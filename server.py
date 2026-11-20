"""
[3주차 L4 TCP 소켓 개편] 2+2N 멀티스레드 순수 TCP 소켓 중앙 서버 (server.py)
- 외부 웹 프레임워크(FastAPI, Uvicorn, WebSocket)를 완전히 제거하고
  Python 표준 라이브러리(socket, threading, queue)만으로 L4 TCP 서버를 구현합니다.
- 스레드 아키텍처 (2 + 2N 모델):
  • Thread 1 (Main Thread): 서버 소켓 초기화, DB 준비 및 종료 제어
  • Thread 2 (Accept Thread): server_sock.accept() 무한 루프로 신규 접속 수락
  • Thread 3 ~ 2+2N (클라이언트 N대당 2개씩):
      1) RxWorker (수신/핸들러 스레드): recv_packet() -> 인증 -> 라우팅 -> DB 처리 -> 큐 적재
      2) TxWorker (송신 전용 Consumer): send_queue.get() -> send_packet()
- Producer-Consumer 패턴 & 브로드캐스트:
  • 워커 스레드는 소켓에 직접 쓰지 않고 대상 클라이언트의 send_queue(Queue)에 적재(Producer)하며,
    전담 TxWorker(Consumer)가 순차 전송하여 다중 스레드 간 소켓 송신 충돌을 방지합니다.
"""

import queue
import socket
import threading
import time
from typing import Any, Dict, List, Optional

from config import SERVER_HOST, SERVER_PORT, SHARED_API_KEY
from database import (
    create_order_transaction,
    fetch_kitchen_orders,
    fetch_menus_by_store,
    fetch_order_by_id,
    init_db,
    update_order_status,
)
from socket_utils import (
    ACTION_CREATE_ORDER,
    ACTION_ERROR,
    ACTION_GET_MENUS,
    ACTION_GET_ORDERS,
    ACTION_NEW_ORDER_BROADCAST,
    ACTION_ORDER_STATUS_BROADCAST,
    ACTION_PING,
    ACTION_PONG,
    ACTION_REGISTER,
    ACTION_UPDATE_ORDER_STATUS,
    make_response,
    recv_packet,
    send_packet,
)


class ClientSession:
    """
    연결된 단일 클라이언트(키오스크 또는 주방 화면)의 소켓과
    전담 2개 스레드(RxWorker, TxWorker), 송신 큐(send_queue)를 캡슐화합니다.
    """

    def __init__(
        self,
        session_id: int,
        sock: socket.socket,
        addr: tuple,
        manager: "ClientManager",
    ) -> None:
        self.session_id = session_id
        self.sock = sock
        self.addr = addr
        self.manager = manager
        self.client_type: str = "unknown"  # "kiosk", "kitchen", "app"
        self.send_queue: queue.Queue[Optional[Dict[str, Any]]] = queue.Queue()
        self.alive = True
        self._close_lock = threading.Lock()

        self.rx_thread = threading.Thread(
            target=self._rx_loop,
            name=f"Client-{session_id}-Rx",
            daemon=True,
        )
        self.tx_thread = threading.Thread(
            target=self._tx_loop,
            name=f"Client-{session_id}-Tx",
            daemon=True,
        )

    def start(self) -> None:
        """클라이언트 전담 Rx/Tx 스레드 2개를 동시에 시작합니다."""
        self.tx_thread.start()
        self.rx_thread.start()

    def enqueue(self, packet: Dict[str, Any]) -> None:
        """Producer: 송신할 패킷을 안전하게 send_queue에 적재합니다."""
        if self.alive:
            self.send_queue.put(packet)

    def close(self) -> None:
        """세션 종료 및 소켓/큐 리소스를 안전하게 정리합니다."""
        with self._close_lock:
            if not self.alive:
                return
            self.alive = False

        # TxWorker 깨우기용 센티널(None) 삽입
        self.send_queue.put(None)
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass

        self.manager.unregister(self)

    def _tx_loop(self) -> None:
        """Consumer: send_queue에서 패킷을 꺼내 L4 TCP 소켓으로 전송합니다."""
        try:
            while self.alive:
                packet = self.send_queue.get()
                if packet is None:
                    break
                send_packet(self.sock, packet)
        except (OSError, ConnectionError) as exc:
            print(f"[Tx-{self.session_id}] 송신 종료 ({self.addr}): {exc}")
        except Exception as exc:
            print(f"[Tx-{self.session_id}] 예기치 않은 송신 오류: {exc}")
        finally:
            self.close()

    def _rx_loop(self) -> None:
        """수신 & 클라이언트 핸들러 파이프라인: 패킷 수신 -> 인증 -> 라우팅 -> 응답/브로드캐스트."""
        try:
            while self.alive:
                packet = recv_packet(self.sock)
                if packet is None:
                    # 상대방의 정상적인 연결 종료(EOF)
                    break
                self._handle_packet(packet)
        except (OSError, ConnectionError, ValueError) as exc:
            if self.alive:
                print(f"[Rx-{self.session_id}] 수신 종료 ({self.addr}): {exc}")
        except Exception as exc:
            print(f"[Rx-{self.session_id}] 패킷 처리 중 오류 ({self.addr}): {exc}")
        finally:
            self.close()

    def _handle_packet(self, packet: Dict[str, Any]) -> None:
        """수신된 요청 패킷의 토큰을 검증하고 액션별로 분기 처리합니다."""
        action = packet.get("action", "")
        request_id = packet.get("request_id")
        auth_token = packet.get("auth_token", "")
        payload = packet.get("payload") or {}

        # 1. 공유 인증 토큰 검사 (SHARED_API_KEY가 설정된 경우)
        if SHARED_API_KEY and auth_token != SHARED_API_KEY:
            self.enqueue(
                make_response(
                    action=ACTION_ERROR,
                    success=False,
                    message="인가되지 않은 클라이언트 접근입니다 (Invalid auth_token).",
                    request_id=request_id,
                    status_code=403,
                )
            )
            return

        # 2. 액션 라우팅
        try:
            if action == ACTION_PING:
                self.enqueue(
                    make_response(
                        action=ACTION_PONG,
                        success=True,
                        data={"timestamp": time.time()},
                        message="PONG",
                        request_id=request_id,
                    )
                )

            elif action == ACTION_REGISTER:
                client_type = str(payload.get("client_type", "unknown")).lower()
                self.client_type = client_type
                print(
                    f"[Server] 클라이언트 등록 완료: Session#{self.session_id} "
                    f"({client_type}, {self.addr})"
                )
                resp_data: Dict[str, Any] = {"client_type": client_type}
                if client_type == "kitchen":
                    resp_data["orders"] = fetch_kitchen_orders()
                self.enqueue(
                    make_response(
                        action=ACTION_REGISTER,
                        success=True,
                        data=resp_data,
                        message=f"{client_type} 클라이언트 등록 완료",
                        request_id=request_id,
                    )
                )

            elif action == ACTION_GET_MENUS:
                store_id = str(payload.get("store_id", ""))
                menus = fetch_menus_by_store(store_id)
                self.enqueue(
                    make_response(
                        action=ACTION_GET_MENUS,
                        success=True,
                        data=menus,
                        message="메뉴 조회 성공",
                        request_id=request_id,
                    )
                )

            elif action == ACTION_CREATE_ORDER:
                result = create_order_transaction(payload)
                order_id = result["order_id"]

                # 키오스크 클라이언트에게 주문 번호 즉시 응답
                self.enqueue(
                    make_response(
                        action=ACTION_CREATE_ORDER,
                        success=True,
                        data=result,
                        message="주문이 성공적으로 접수되었습니다.",
                        request_id=request_id,
                    )
                )

                # 주방 화면(kitchen) 클라이언트들에게 실시간 신규 주문 브로드캐스트
                full_order = fetch_order_by_id(order_id)
                broadcast_data = full_order if full_order else {
                    "order_id": order_id,
                    "store_id": result["store_id"],
                    "store_name": result["store_name"],
                    "total_price": result["total_price"],
                    "order_type": payload.get("order_type", "매장"),
                    "spoon_needed": payload.get("spoon_needed", "필요없음"),
                    "status": "PENDING",
                    "items": payload.get("items", []),
                }
                self.manager.broadcast(
                    target_type="kitchen",
                    packet=make_response(
                        action=ACTION_NEW_ORDER_BROADCAST,
                        success=True,
                        data=broadcast_data,
                        message=f"[{result['store_name']}] 신규 주문 #{order_id}이 접수되었습니다.",
                    ),
                )

            elif action == ACTION_GET_ORDERS:
                orders = fetch_kitchen_orders()
                self.enqueue(
                    make_response(
                        action=ACTION_GET_ORDERS,
                        success=True,
                        data=orders,
                        message="주방 주문 목록 조회 성공",
                        request_id=request_id,
                    )
                )

            elif action == ACTION_UPDATE_ORDER_STATUS:
                order_id = int(payload["order_id"])
                new_status = str(payload["new_status"]).upper()
                if new_status not in ("PENDING", "COOKING", "COMPLETED"):
                    raise ValueError(f"허용되지 않는 주문 상태입니다: {new_status}")

                updated = update_order_status(order_id, new_status)
                if not updated:
                    self.enqueue(
                        make_response(
                            action=ACTION_UPDATE_ORDER_STATUS,
                            success=False,
                            message=f"주문 번호 #{order_id}를 찾을 수 없습니다.",
                            request_id=request_id,
                            status_code=404,
                        )
                    )
                    return

                self.enqueue(
                    make_response(
                        action=ACTION_UPDATE_ORDER_STATUS,
                        success=True,
                        data={"order_id": order_id, "new_status": new_status},
                        message=f"주문 #{order_id} 상태가 {new_status}(으)로 변경되었습니다.",
                        request_id=request_id,
                    )
                )

                # 주방 및 모바일 앱 클라이언트에 상태 변경 브로드캐스트
                status_packet = make_response(
                    action=ACTION_ORDER_STATUS_BROADCAST,
                    success=True,
                    data={"order_id": order_id, "new_status": new_status},
                    message=f"주문 #{order_id} 상태 변경: {new_status}",
                )
                self.manager.broadcast("kitchen", status_packet)
                self.manager.broadcast("app", status_packet)

            else:
                self.enqueue(
                    make_response(
                        action=ACTION_ERROR,
                        success=False,
                        message=f"알 수 없는 요청 액션입니다: {action}",
                        request_id=request_id,
                        status_code=400,
                    )
                )

        except ValueError as ve:
            self.enqueue(
                make_response(
                    action=action or ACTION_ERROR,
                    success=False,
                    message=str(ve),
                    request_id=request_id,
                    status_code=400,
                )
            )
        except Exception as exc:
            self.enqueue(
                make_response(
                    action=action or ACTION_ERROR,
                    success=False,
                    message=f"서버 내부 오류: {exc}",
                    request_id=request_id,
                    status_code=500,
                )
            )


class ClientManager:
    """활성 ClientSession 목록을 Thread-safe하게 관리하고 브로드캐스트를 수행합니다."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: List[ClientSession] = []
        self._next_id = 1

    def create_session(self, sock: socket.socket, addr: tuple) -> ClientSession:
        with self._lock:
            session = ClientSession(self._next_id, sock, addr, self)
            self._next_id += 1
            self._sessions.append(session)
            total_clients = len(self._sessions)
        print(
            f"[Accept] 새 클라이언트 연결: Session#{session.session_id} {addr} "
            f"(현재 접속 N={total_clients}, 총 서버 스레드 2+2N={2 + 2 * total_clients})"
        )
        return session

    def unregister(self, session: ClientSession) -> None:
        with self._lock:
            if session in self._sessions:
                self._sessions.remove(session)
                total_clients = len(self._sessions)
                print(
                    f"[Disconnect] 연결 해제: Session#{session.session_id} ({session.client_type}) "
                    f"(남은 접속 N={total_clients})"
                )

    def broadcast(self, target_type: str, packet: Dict[str, Any]) -> None:
        """특정 유형(예: 'kitchen')의 모든 활성 세션 send_queue에 패킷을 적재합니다."""
        with self._lock:
            targets = [s for s in self._sessions if s.alive and s.client_type == target_type]
        for session in targets:
            session.enqueue(packet)

    def close_all(self) -> None:
        with self._lock:
            sessions_copy = list(self._sessions)
        for session in sessions_copy:
            session.close()


class TCPKioskServer:
    """2+2N 멀티스레드 L4 TCP 소켓 중앙 서버."""

    def __init__(self, host: str = SERVER_HOST, port: int = SERVER_PORT) -> None:
        self.host = host
        self.port = port
        self.manager = ClientManager()
        self.server_sock: Optional[socket.socket] = None
        self.running = False
        self.accept_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        init_db()
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(16)
        self.server_sock.settimeout(1.0)
        self.running = True

        # Thread 2: Accept Thread 시작
        self.accept_thread = threading.Thread(
            target=self._accept_loop,
            name="Server-Accept-Thread",
            daemon=True,
        )
        self.accept_thread.start()

        print("============================================================")
        print(" [L4 TCP] 보다수 멀티스레드 소켓 중앙 서버를 시작합니다!")
        print(f" • 바인딩 주소:   {self.host}:{self.port} (AF_INET, SOCK_STREAM)")
        print(" • 스레드 모델:   2 + 2N (Main + Accept + 클라이언트당 Rx/Tx)")
        print(" • DB 동기화:     threading.Lock() (Mutex) + SQLite WAL 트랜잭션")
        print("============================================================")

    def _accept_loop(self) -> None:
        """Thread 2: 신규 클라이언트 TCP 연결을 수락하고 2개의 워커 스레드를 할당합니다."""
        assert self.server_sock is not None
        while self.running:
            try:
                client_sock, addr = self.server_sock.accept()
                session = self.manager.create_session(client_sock, addr)
                session.start()
            except socket.timeout:
                continue
            except OSError:
                if self.running:
                    continue
                break

    def serve_forever(self) -> None:
        """Thread 1 (Main Thread): 종료 시그널(Ctrl+C)까지 서버 상태를 유지합니다."""
        self.start()
        try:
            while self.running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n[Server] 종료 요청을 감지했습니다. 안전하게 종료합니다...")
        finally:
            self.stop()

    def stop(self) -> None:
        self.running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except OSError:
                pass
        self.manager.close_all()
        print("[Server] 모든 소켓 및 스레드 리소스를 정리했습니다.")


if __name__ == "__main__":
    server = TCPKioskServer()
    server.serve_forever()
