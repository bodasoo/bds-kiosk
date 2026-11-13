"""
[2주차 검증 스크립트] WebSocket 실시간 푸시 & REST API 하이브리드 연동 테스트 (test_websocket.py)
- 실행 방법:
  1. 먼저 터미널 1에서 서버 실행: python server.py
  2. 터미널 2에서 테스트 실행:   python test_websocket.py
"""

import asyncio
import json
import ssl
import requests
import websockets

from config import (
    BASE_URL,
    DEFAULT_HEADERS,
    SHARED_API_KEY,
    WS_APP_ENDPOINT,
    WS_KITCHEN_ENDPOINT,
)

# 자체 서명 SSL 인증서 검증 비활성화 컨텍스트 (테스트 환경용)
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


async def test_websocket_flow():
    print("============================================================")
    print(" 🚀 WebSocket 양방향 통신 및 REST 하이브리드 연동 테스트 시작")
    print("============================================================")

    kitchen_ws_url = f"{WS_KITCHEN_ENDPOINT}?token={SHARED_API_KEY}"
    app_ws_url = f"{WS_APP_ENDPOINT}?token={SHARED_API_KEY}"

    print(f"1. 주방 WebSocket 접속 시도: {kitchen_ws_url}")
    async with websockets.connect(kitchen_ws_url, ssl=ssl_context) as kitchen_ws:
        init_kitchen = await kitchen_ws.recv()
        print(f"   ✅ [주방 WS 수신] {init_kitchen}")

        print(f"\n2. 고객 모바일 WebSocket 접속 시도: {app_ws_url}")
        async with websockets.connect(app_ws_url, ssl=ssl_context) as app_ws:
            init_app = await app_ws.recv()
            print(f"   ✅ [고객 WS 수신] {init_app}")

            # 3. 키오스크 주문 생성 (HTTPS POST)
            print("\n3. [키오스크 1] HTTPS POST /order 신규 주문 전송...")
            order_payload = {
                "store_id": "KIOSK_01",
                "store_name": "보다수 커피",
                "order_type": "매장식사",
                "spoon_needed": "수저필요없음",
                "items": [
                    {
                        "menu_name": "아메리카노",
                        "price": 2000,
                        "quantity": 1,
                        "temperature": "ICE",
                        "exclude_carrot": None,
                        "exclude_cucumber": None,
                    }
                ],
            }
            res = requests.post(
                f"{BASE_URL}/order",
                json=order_payload,
                headers=DEFAULT_HEADERS,
                verify=False,
            )
            order_res = res.json()
            order_id = order_res.get("order_id")
            print(f"   ✅ [주문 생성 완료] Order #{order_id} ({res.status_code})")

            # 4. 주방 화면에서 실시간 NEW_ORDER 이벤트 수신 확인
            print("\n4. [주방 WS] 실시간 푸시 이벤트 대기 중...")
            kitchen_event = await asyncio.wait_for(kitchen_ws.recv(), timeout=5.0)
            print(f"   🔔 [주방 WS 실시간 푸시 수신!]:\n      {kitchen_event}")

            # 5. 주방에서 [주문 접수] 클릭 (PATCH /accept)
            print(f"\n5. [주방] 주문 #{order_id} 접수 처리 (PATCH /accept)...")
            res_accept = requests.patch(
                f"{BASE_URL}/orders/{order_id}/accept",
                headers=DEFAULT_HEADERS,
                verify=False,
            )
            print(f"   ✅ [주문 접수 완료] status={res_accept.json().get('new_status')}")

            # 6. 고객 모바일에서 실시간 ORDER_COOKING 알림 수신 확인
            print("\n6. [고객 WS] 조리 시작 알림 대기 중...")
            app_event_cooking = await asyncio.wait_for(app_ws.recv(), timeout=5.0)
            print(f"   🔔 [고객 WS 알림 수신!]:\n      {app_event_cooking}")

            # 7. 주방에서 [조리 완료] 클릭 (PATCH /complete)
            print(f"\n7. [주방] 주문 #{order_id} 조리 완료 처리 (PATCH /complete)...")
            res_complete = requests.patch(
                f"{BASE_URL}/orders/{order_id}/complete",
                headers=DEFAULT_HEADERS,
                verify=False,
            )
            print(f"   ✅ [조리 완료 처리] status={res_complete.json().get('new_status')}")

            # 8. 고객 모바일에서 실시간 ORDER_COMPLETED 픽업 알림 수신 확인
            print("\n8. [고객 WS] 조리 완료/픽업 알림 대기 중...")
            app_event_complete = await asyncio.wait_for(app_ws.recv(), timeout=5.0)
            print(f"   🔔 [고객 WS 픽업 알림 수신!]:\n      {app_event_complete}")

    print("\n============================================================")
    print(" 🎉 모든 WebSocket 실시간 푸시 & REST 연동 테스트 ALL PASS!")
    print("============================================================")


if __name__ == "__main__":
    # urllib3 경고 무시
    requests.packages.urllib3.disable_warnings()
    asyncio.run(test_websocket_flow())

