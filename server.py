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
from fastapi import Depends, FastAPI, HTTPException, Security, status
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
def create_order(order_req: OrderCreateRequest):
    """[API 2] 키오스크 1·2 신규 주문 생성 (SQLite 트랜잭션 저장)"""
    try:
        result = create_order_transaction(order_req.model_dump())
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
    """[API 3] 주방 화면 1~2초 주기 폴링: 미접수(PENDING) 및 조리중(COOKING) 주문 목록 조회"""
    return fetch_kitchen_orders()


@app.patch(
    "/orders/{order_id}/accept",
    response_model=OrderStatusUpdateResponse,
    dependencies=[Depends(verify_api_key)],
)
def accept_order(order_id: int):
    """[API 4] 주방 화면 [주문 접수] 버튼 처리 (PENDING -> COOKING)"""
    ok = update_order_status(order_id, "COOKING")
    if not ok:
        raise HTTPException(status_code=404, detail=f"주문 번호 #{order_id}를 찾을 수 없습니다.")
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
def complete_order(order_id: int):
    """[API 5] 주방 화면 [조리 완료] 버튼 처리 (COOKING -> COMPLETED)"""
    ok = update_order_status(order_id, "COMPLETED")
    if not ok:
        raise HTTPException(status_code=404, detail=f"주문 번호 #{order_id}를 찾을 수 없습니다.")
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
    """[API 6] 고객용 가상 모바일 폰 1~2초 주기 폴링: 신규 접수/조리완료 알림 조회"""
    return fetch_and_mark_notifications()


if __name__ == "__main__":
    # 인증서 파일이 없을 경우 자동 생성
    if not (os.path.exists(SSL_CERT_FILE) and os.path.exists(SSL_KEY_FILE)):
        generate_self_signed_cert()

    init_db()
    print(f"============================================================")
    print(f" 🔒 중앙 관리 서버(FastAPI + HTTPS)를 시작합니다!")
    print(f" • 접속 주소: https://{SERVER_HOST}:{SERVER_PORT}")
    print(f" • API 문서:  https://{SERVER_HOST}:{SERVER_PORT}/docs")
    print(f"============================================================")
    uvicorn.run(
        app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        ssl_keyfile=SSL_KEY_FILE,
        ssl_certfile=SSL_CERT_FILE,
    )

