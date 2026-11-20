"""
[3주차 L4 TCP 소켓 개편] 순수 TCP 패킷 프레이밍 및 송수신 유틸리티 (socket_utils.py)
- TCP(SOCK_STREAM)는 메시지 경계가 없는 바이트 스트림이므로,
  패킷 뭉침(Coalescing)과 쪼개짐(Fragmentation)을 방지하기 위해
  [4바이트 길이 헤더(Big-Endian, >I) + UTF-8 JSON 페이로드] 규격을 사용합니다.
- 외부 웹 프레임워크 없이 Python 표준 라이브러리(socket, struct, json, uuid)만 사용합니다.
"""

import json
import socket
import struct
import uuid
from typing import Any, Optional

from config import (
    BUFFER_SIZE,
    ENCODING,
    HEADER_FORMAT,
    HEADER_SIZE,
    MAX_PACKET_SIZE,
    SOCKET_TIMEOUT,
)

# ==========================================
# 프로토콜 액션(명령) 상수 정의
# ==========================================
ACTION_REGISTER = "REGISTER"                          # 클라이언트 유형 등록 (kiosk / kitchen)
ACTION_GET_MENUS = "GET_MENUS"                        # 매장별 메뉴 목록 조회
ACTION_CREATE_ORDER = "CREATE_ORDER"                  # 신규 주문 생성 및 결제 처리
ACTION_GET_ORDERS = "GET_ORDERS"                      # 주방용 주문 목록 조회
ACTION_UPDATE_ORDER_STATUS = "UPDATE_ORDER_STATUS"    # 주문 상태 변경 (PENDING -> PREPARING -> COMPLETED)
ACTION_NEW_ORDER_BROADCAST = "NEW_ORDER_BROADCAST"    # 서버 -> 주방 실시간 신규 주문 브로드캐스트
ACTION_ORDER_STATUS_BROADCAST = "ORDER_STATUS_BROADCAST"  # 서버 -> 클라이언트 주문 상태 변경 브로드캐스트
ACTION_PING = "PING"                                  # 연결 상태 확인(Heartbeat)
ACTION_PONG = "PONG"                                  # Heartbeat 응답
ACTION_ERROR = "ERROR"                                # 오류 응답


def pack_message(data: dict[str, Any]) -> bytes:
    """딕셔너리를 UTF-8 JSON 바이트로 직렬화하고 4바이트 길이 헤더를 부착합니다."""
    body = json.dumps(data, ensure_ascii=False).encode(ENCODING)
    body_len = len(body)
    if body_len > MAX_PACKET_SIZE:
        raise ValueError(f"Packet size {body_len} exceeds MAX_PACKET_SIZE ({MAX_PACKET_SIZE})")
    header = struct.pack(HEADER_FORMAT, body_len)
    return header + body


def recv_exact(sock: socket.socket, num_bytes: int) -> Optional[bytes]:
    """
    소켓에서 정확히 num_bytes 바이트를 읽을 때까지 반복 recv()를 수행합니다.
    - 시작 전에 정상 종료(EOF)되면 None을 반환합니다.
    - 데이터를 일부만 읽은 상태에서 연결이 끊어지면 ConnectionError를 발생시킵니다.
    """
    chunks: list[bytes] = []
    bytes_received = 0

    while bytes_received < num_bytes:
        remaining = num_bytes - bytes_received
        chunk = sock.recv(min(BUFFER_SIZE, remaining))
        if not chunk:
            if bytes_received == 0:
                return None
            raise ConnectionError(
                f"Socket closed prematurely: expected {num_bytes} bytes, got {bytes_received} bytes"
            )
        chunks.append(chunk)
        bytes_received += len(chunk)

    return b"".join(chunks)


def send_packet(sock: socket.socket, data: dict[str, Any]) -> None:
    """프레이밍된 패킷을 소켓 전체 전송(sendall)으로 송신합니다."""
    frame = pack_message(data)
    sock.sendall(frame)


def recv_packet(sock: socket.socket) -> Optional[dict[str, Any]]:
    """
    4바이트 길이 헤더를 먼저 읽은 뒤 해당 길이만큼 바디를 읽어 딕셔너리로 복원합니다.
    - 상대방이 정상적으로 연결을 종료하면 None을 반환합니다.
    """
    header = recv_exact(sock, HEADER_SIZE)
    if header is None:
        return None

    (payload_len,) = struct.unpack(HEADER_FORMAT, header)
    if payload_len == 0 or payload_len > MAX_PACKET_SIZE:
        raise ValueError(f"Invalid payload length: {payload_len}")

    body = recv_exact(sock, payload_len)
    if body is None:
        raise ConnectionError("Socket closed while reading packet body")

    return json.loads(body.decode(ENCODING))


def make_request(
    action: str,
    payload: Optional[dict[str, Any]] = None,
    auth_token: str = "",
    request_id: Optional[str] = None,
) -> dict[str, Any]:
    """표준 요청 패킷 딕셔너리를 생성합니다."""
    return {
        "type": "REQUEST",
        "action": action,
        "request_id": request_id or str(uuid.uuid4()),
        "auth_token": auth_token,
        "payload": payload or {},
    }


def make_response(
    action: str,
    success: bool,
    data: Any = None,
    message: str = "",
    request_id: Optional[str] = None,
    status_code: int = 200,
) -> dict[str, Any]:
    """표준 응답 패킷 딕셔너리를 생성합니다."""
    return {
        "type": "RESPONSE",
        "action": action,
        "request_id": request_id,
        "success": success,
        "status_code": status_code,
        "message": message,
        "data": data,
    }


def send_request(
    host: str,
    port: int,
    action: str,
    payload: Optional[dict[str, Any]] = None,
    auth_token: str = "",
    timeout: float = SOCKET_TIMEOUT,
) -> dict[str, Any]:
    """
    단발성 요청-응답 TCP 소켓 통신을 수행합니다. (주로 키오스크 백그라운드 스레드에서 사용)
    연결 -> 패킷 송신 -> 응답 패킷 수신 -> 연결 종료까지 안전하게 처리합니다.
    """
    req = make_request(action=action, payload=payload, auth_token=auth_token)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect((host, port))
        send_packet(sock, req)
        resp = recv_packet(sock)
        if resp is None:
            raise ConnectionError("Server closed connection without sending a response")
        return resp
