"""
[3주차 L4 TCP 소켓 개편] 멀티스레드 TCP 서버 & DB Mutex Lock 통합 검증 스크립트 (test_tcp_server.py)
- 2+2N 스레드 서버, Length-Prefix 패킷 프레이밍, 주방 실시간 브로드캐스트,
  다중 키오스크 동시 주문 시 db_lock(Mutex) 동기화를 한 번에 검증합니다.
"""

import socket
import threading

from config import SHARED_API_KEY
from server import TCPKioskServer
from socket_utils import (
    ACTION_CREATE_ORDER,
    ACTION_GET_MENUS,
    ACTION_NEW_ORDER_BROADCAST,
    ACTION_REGISTER,
    ACTION_UPDATE_ORDER_STATUS,
    make_request,
    recv_packet,
    send_packet,
    send_request,
)


def run_integration_test() -> None:
    server = TCPKioskServer(host="127.0.0.1", port=0)
    server.start()
    assert server.server_sock is not None
    port = server.server_sock.getsockname()[1]
    print(f"[TEST] 임시 TCP 테스트 서버 시작: 127.0.0.1:{port}")

    try:
        # 1. 주방 클라이언트 지속 연결 및 REGISTER
        kitchen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        kitchen_sock.settimeout(3.0)
        kitchen_sock.connect(("127.0.0.1", port))
        send_packet(
            kitchen_sock,
            make_request(
                ACTION_REGISTER,
                payload={"client_type": "kitchen"},
                auth_token=SHARED_API_KEY,
            ),
        )
        reg_resp = recv_packet(kitchen_sock)
        assert reg_resp is not None and reg_resp["success"] is True
        print("[TEST 1/4] 주방 클라이언트 REGISTER 및 초기 주문 동기화 성공")

        # 2. 매장 메뉴 조회 검증
        menu_resp = send_request(
            "127.0.0.1",
            port,
            ACTION_GET_MENUS,
            payload={"store_id": "KIOSK_01"},
            auth_token=SHARED_API_KEY,
        )
        assert menu_resp["success"] is True and len(menu_resp["data"]) == 12
        print("[TEST 2/4] KIOSK_01 메뉴 12종 TCP 조회 성공")

        # 3. 키오스크 1·2 동시 주문 스트레스 테스트 (Mutex Lock 검증)
        order_ids = []
        errors = []

        def place_order(store_id: str, store_name: str, menu_name: str, price: int) -> None:
            try:
                resp = send_request(
                    "127.0.0.1",
                    port,
                    ACTION_CREATE_ORDER,
                    payload={
                        "store_id": store_id,
                        "store_name": store_name,
                        "order_type": "포장",
                        "spoon_needed": "수저필요없음",
                        "items": [
                            {
                                "menu_name": menu_name,
                                "price": price,
                                "quantity": 1,
                            }
                        ],
                    },
                    auth_token=SHARED_API_KEY,
                )
                assert resp["success"] is True
                order_ids.append(resp["data"]["order_id"])
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=place_order, args=("KIOSK_01", "보다수 커피", "아메리카노", 3000))
        t2 = threading.Thread(target=place_order, args=("KIOSK_02", "김밥천국", "기본 김밥", 3000))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors, f"동시 주문 오류 발생: {errors}"
        assert len(order_ids) == 2 and len(set(order_ids)) == 2
        print(f"[TEST 3/4] 다중 키오스크 동시 주문 Mutex Lock 직렬화 성공: order_ids={order_ids}")

        # 4. 주방 실시간 브로드캐스트 수신 및 상태 변경 검증
        broadcasts = []
        for _ in range(2):
            pkt = recv_packet(kitchen_sock)
            assert pkt is not None and pkt["action"] == ACTION_NEW_ORDER_BROADCAST
            broadcasts.append(pkt["data"]["order_id"])

        assert set(broadcasts) == set(order_ids)

        upd_resp = send_request(
            "127.0.0.1",
            port,
            ACTION_UPDATE_ORDER_STATUS,
            payload={"order_id": order_ids[0], "new_status": "COMPLETED"},
            auth_token=SHARED_API_KEY,
        )
        assert upd_resp["success"] is True
        kitchen_sock.close()
        print("[TEST 4/4] 주방 실시간 브로드캐스트 및 상태 변경 성공")
        print("\n=== ALL L4 TCP INTEGRATION TESTS PASSED ===")
    finally:
        server.stop()


if __name__ == "__main__":
    run_integration_test()
