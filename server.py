"""
[중앙 관리 서버 - server.py]
- 프레임워크: FastAPI + Uvicorn
- 보안 설계:
  1) HTTPS (SSL/TLS): 자체 서명 인증서(cert.pem, key.pem) 적용
  2) API Key 인증: HTTP 헤더(access_token)를 FastAPI Security(APIKeyHeader)로 검증
- 데이터베이스: SQLite (kiosk.db, WAL 모드 및 ACID 트랜잭션 기반 동시성 제어)
"""

import os
from typing import List
import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Security,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.security.api_key import APIKeyHeader

from config import (
    API_KEY_HEADER_NAME,
    SERVER_HOST,
    SERVER_PORT,
    SHARED_API_KEY,
    SSL_CERT_FILE,
    SSL_KEY_FILE,
)
from database import (
    create_order_transaction,
    fetch_and_mark_notifications,
    fetch_kitchen_orders,
    fetch_menus_by_store,
    init_db,
    update_order_status,
)
from generate_cert import generate_self_signed_cert
from schemas import (
    KitchenOrderResponse,
    MenuItemSchema,
    MobileNotificationItem,
    OrderCreateRequest,
    OrderCreateResponse,
    OrderStatusUpdateResponse,
)

app = FastAPI(
    title="🛒 멀티 클라이언트 키오스크 및 주방/고객 연동 중앙 서버",
    description="HTTPS(SSL/TLS) 및 API Key(access_token) 인증 기반 중앙 주문/조리/알림 관리 API",
    version="1.0.0",
)

# ==========================================
# API Key 보안 헤더 검증 (FastAPI Security)
# ==========================================
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """클라이언트 요청 헤더의 access_token 값을 검증합니다."""
    if not api_key or api_key != SHARED_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="인가되지 않은 클라이언트 접근입니다 (Invalid or missing access_token).",
        )
    return api_key


# ==========================================
# WebSocket 양방향 브로드캐스트 연결 관리자
# ==========================================
class ConnectionManager:
    """주방 디스플레이(KDS) 및 고객 모바일 앱의 실시간 소켓 연결을 통합 관리합니다."""

    def __init__(self):
        self.kitchen_sockets: List[WebSocket] = []
        self.app_sockets: List[WebSocket] = []

    async def connect_kitchen(self, websocket: WebSocket):
        await websocket.accept()
        self.kitchen_sockets.append(websocket)
        print(f"👨‍🍳 [WebSocket] 주방 화면 연결됨 (활성 연결: {len(self.kitchen_sockets)}대)")

    def disconnect_kitchen(self, websocket: WebSocket):
        if websocket in self.kitchen_sockets:
            self.kitchen_sockets.remove(websocket)
            print(f"👨‍🍳 [WebSocket] 주방 화면 연결 해제 (남은 연결: {len(self.kitchen_sockets)}대)")

    async def connect_app(self, websocket: WebSocket):
        await websocket.accept()
        self.app_sockets.append(websocket)
        print(f"📱 [WebSocket] 고객 모바일 앱 연결됨 (활성 연결: {len(self.app_sockets)}대)")

    def disconnect_app(self, websocket: WebSocket):
        if websocket in self.app_sockets:
            self.app_sockets.remove(websocket)
            print(f"📱 [WebSocket] 고객 모바일 앱 연결 해제 (남은 연결: {len(self.app_sockets)}대)")

    async def broadcast_to_kitchen(self, message: dict):
        """연결된 모든 주방 화면으로 신규 주문 또는 상태 변경 이벤트 즉시 전송 (Server Push)"""
        dead_sockets = []
        for ws in self.kitchen_sockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead_sockets.append(ws)
        for ws in dead_sockets:
            self.disconnect_kitchen(ws)

    async def broadcast_to_app(self, message: dict):
        """연결된 모든 고객 모바일 단말기로 조리 시작/픽업 완료 알림 즉시 전송 (Server Push)"""
        dead_sockets = []
        for ws in self.app_sockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead_sockets.append(ws)
        for ws in dead_sockets:
            self.disconnect_app(ws)


manager = ConnectionManager()


@app.on_event("startup")
def on_startup() -> None:
    """서버 시작 시 SQLite DB 및 23종 초기 메뉴 자동 초기화"""
    init_db()


# ==========================================
# 핵심 REST API 엔드포인트 (6종)
# ==========================================
@app.get("/health")
def health_check() -> dict:
    """서버 동작 상태 확인 엔드포인트"""
    return {"status": "running", "https": True}


@app.get(
    "/menus/{store_id}",
    response_model=List[MenuItemSchema],
    dependencies=[Depends(verify_api_key)],
)
def get_store_menus(store_id: str):
    """[API 1] 매장별(KIOSK_01 / KIOSK_02) 전체 메뉴 조회"""
    return fetch_menus_by_store(store_id)


@app.post(
    "/order",
    response_model=OrderCreateResponse,
    dependencies=[Depends(verify_api_key)],
)
async def create_order(order_req: OrderCreateRequest):
    """[API 2] 키오스크 1·2 신규 주문 생성 (SQLite 트랜잭션 저장 + 주방 WebSocket 실시간 푸시)"""
    try:
        result = create_order_transaction(order_req.model_dump())

        # [WebSocket Server Push] 주방 화면으로 신규 주문 실시간 브로드캐스트
        await manager.broadcast_to_kitchen({
            "event": "NEW_ORDER",
            "order_id": result["order_id"],
            "store_id": result["store_id"],
            "store_name": result["store_name"],
            "total_price": result["total_price"],
            "order_type": order_req.order_type,
            "spoon_needed": order_req.spoon_needed,
            "items": [item.model_dump() for item in order_req.items],
            "message": f"[{result['store_name']}] 신규 주문 #{result['order_id']}이 접수되었습니다.",
        })

        return OrderCreateResponse(
            status="OK",
            order_id=result["order_id"],
            store_id=result["store_id"],
            store_name=result["store_name"],
            total_price=result["total_price"],
            message="주문이 성공적으로 접수되었습니다.",
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"주문 저장 오류: {exc}")


@app.get(
    "/orders/kitchen",
    response_model=List[KitchenOrderResponse],
    dependencies=[Depends(verify_api_key)],
)
def get_kitchen_orders():
    """[API 3] 주방 화면 폴링 조회: 미접수(PENDING) 및 조리중(COOKING) 주문 목록 조회"""
    return fetch_kitchen_orders()


@app.patch(
    "/orders/{order_id}/accept",
    response_model=OrderStatusUpdateResponse,
    dependencies=[Depends(verify_api_key)],
)
async def accept_order(order_id: int):
    """[API 4] 주방 화면 [주문 접수] 처리 (PENDING -> COOKING + 고객 모바일 실시간 알림 푸시)"""
    ok = update_order_status(order_id, "COOKING")
    if not ok:
        raise HTTPException(status_code=404, detail=f"주문 번호 #{order_id}를 찾을 수 없습니다.")

    # [WebSocket Server Push] 고객 모바일로 조리 시작 알림 푸시
    await manager.broadcast_to_app({
        "event": "ORDER_COOKING",
        "order_id": order_id,
        "status": "COOKING",
        "message": f"주문 #{order_id} 조리가 시작되었습니다. 잠시만 기다려주세요!",
    })
    # 주방 화면에도 상태 동기화 이벤트 푸시
    await manager.broadcast_to_kitchen({
        "event": "ORDER_STATUS_CHANGED",
        "order_id": order_id,
        "new_status": "COOKING",
    })

    return OrderStatusUpdateResponse(
        status="OK",
        order_id=order_id,
        new_status="COOKING",
        message=f"주문 #{order_id} 접수 완료 (조리 시작)",
    )


@app.patch(
    "/orders/{order_id}/complete",
    response_model=OrderStatusUpdateResponse,
    dependencies=[Depends(verify_api_key)],
)
async def complete_order(order_id: int):
    """[API 5] 주방 화면 [조리 완료] 처리 (COOKING -> COMPLETED + 고객 모바일 픽업 알림 푸시)"""
    ok = update_order_status(order_id, "COMPLETED")
    if not ok:
        raise HTTPException(status_code=404, detail=f"주문 번호 #{order_id}를 찾을 수 없습니다.")

    # [WebSocket Server Push] 고객 모바일로 픽업 완료 알림 푸시
    await manager.broadcast_to_app({
        "event": "ORDER_COMPLETED",
        "order_id": order_id,
        "status": "COMPLETED",
        "message": f"주문 #{order_id} 메뉴가 준비되었습니다! 픽업대에서 수령해 주세요 🔔",
    })
    # 주방 화면에도 상태 동기화 이벤트 푸시
    await manager.broadcast_to_kitchen({
        "event": "ORDER_STATUS_CHANGED",
        "order_id": order_id,
        "new_status": "COMPLETED",
    })

    return OrderStatusUpdateResponse(
        status="OK",
        order_id=order_id,
        new_status="COMPLETED",
        message=f"주문 #{order_id} 조리 완료 (고객 픽업 알림 생성)",
    )


@app.get(
    "/orders/notifications",
    response_model=List[MobileNotificationItem],
    dependencies=[Depends(verify_api_key)],
)
def get_mobile_notifications():
    """[API 6] 고객용 가상 모바일 폰 폴링 조회 (하위 호환 유지)"""
    return fetch_and_mark_notifications()


# ==========================================
# WebSocket 양방향 실시간 이벤트 엔드포인트
# ==========================================
@app.websocket("/ws/kitchen")
async def websocket_kitchen_endpoint(websocket: WebSocket, token: str = Query(None)):
    """[WebSocket 1] 주방 디스플레이(KDS) 실시간 채널: 신규 주문 발생 시 서버가 즉시 푸시"""
    if token != SHARED_API_KEY:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect_kitchen(websocket)
    try:
        # 최초 연결 시 현재 대기/조리중인 전체 주문 목록을 즉시 1회 전송 (초기 화면 동기화)
        initial_orders = fetch_kitchen_orders()
        await websocket.send_json({
            "event": "INIT_ORDERS",
            "orders": [o.model_dump() if hasattr(o, "model_dump") else o for o in initial_orders],
            "message": "주방 초기 주문 동기화 완료",
        })
        while True:
            # 주방 클라이언트의 메시지(핑/명령) 수신 대기
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_kitchen(websocket)
    except Exception:
        manager.disconnect_kitchen(websocket)


@app.websocket("/ws/app")
async def websocket_app_endpoint(websocket: WebSocket, token: str = Query(None)):
    """[WebSocket 2] 고객 모바일 앱 실시간 채널: 조리시작/조리완료 시 서버가 즉시 푸시"""
    if token != SHARED_API_KEY:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect_app(websocket)
    try:
        await websocket.send_json({
            "event": "INIT_APP",
            "message": "고객 실시간 알림 채널 연결 완료",
        })
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_app(websocket)
    except Exception:
        manager.disconnect_app(websocket)


if __name__ == "__main__":
    # 인증서 파일이 없을 경우 자동 생성
    if not (os.path.exists(SSL_CERT_FILE) and os.path.exists(SSL_KEY_FILE)):
        generate_self_signed_cert()

    init_db()
    print(f"============================================================")
    print(f" 🔒 중앙 관리 서버(FastAPI + HTTPS + WebSocket)를 시작합니다!")
    print(f" • REST API 주소:     https://{SERVER_HOST}:{SERVER_PORT}")
    print(f" • 주방 WebSocket:    wss://{SERVER_HOST}:{SERVER_PORT}/ws/kitchen")
    print(f" • 고객앱 WebSocket:  wss://{SERVER_HOST}:{SERVER_PORT}/ws/app")
    print(f" • Swagger UI 문서:   https://{SERVER_HOST}:{SERVER_PORT}/docs")
    print(f"============================================================")
    uvicorn.run(
        app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        ssl_keyfile=SSL_KEY_FILE,
        ssl_certfile=SSL_CERT_FILE,
    )

