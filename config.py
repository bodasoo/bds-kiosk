"""
[3주차 L4 TCP 소켓 개편] 공통 환경 설정 모듈 (config.py)
- 중앙 TCP 소켓 서버(server.py)와 클라이언트(키오스크 1·2, 주방 화면)가
  공통으로 참조하는 L4 TCP 네트워크, 패킷 프레이밍, 보안 토큰, SQLite DB 설정값을 정의합니다.
"""

import os

# 프로젝트 기본 경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# .env 파일 자동 로드 (키값 노출 방지 및 환경변수 주입)
ENV_FILE = os.path.join(BASE_DIR, ".env")
if os.path.exists(ENV_FILE):
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())
    except Exception:
        pass

# ==========================================
# 1. 순수 TCP 소켓 서버 네트워크 설정 (L4 계층)
# ==========================================
SERVER_HOST = os.getenv("BDS_SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("BDS_SERVER_PORT", "9000"))

# ==========================================
# 2. L4 바이트 스트림 패킷 프레이밍 규격
# ==========================================
# [ 4-byte Big-Endian Length Header (>I) ] + [ N-byte UTF-8 Payload ]
HEADER_FORMAT = ">I"
HEADER_SIZE = 4
BUFFER_SIZE = 4096
ENCODING = "utf-8"
MAX_PACKET_SIZE = 10 * 1024 * 1024  # 단일 패킷 최대 10MB 제한 (비정상 헤더 방어)

# 소켓 타임아웃 및 재연결 설정 (초 단위)
SOCKET_TIMEOUT = 10.0
RECONNECT_INTERVAL = 2.0

# ==========================================
# 3. 패킷 기반 공유 인증 토큰 설정
# ==========================================
# 키값은 절대 코드에 하드코딩하지 않고 .env 및 환경변수(os.getenv)에서만 가져옵니다.
SHARED_API_KEY = os.getenv("BDS_API_KEY", "")

# ==========================================
# 4. SQLite 데이터베이스 파일 경로 설정 (Python 기본 내장)
# ==========================================
SQLITE_DB_PATH = os.path.join(BASE_DIR, "kiosk.db")
