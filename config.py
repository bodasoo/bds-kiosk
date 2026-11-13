"""
[1주차 산출물] 공통 환경 설정 및 보안/DB 설정 모듈 (config.py)
- 중앙 서버(server.py)와 4개의 클라이언트(키오스크 1·2, 주방 화면, 고객용 가상 모바일 폰)가
  공통으로 참조하는 네트워크, 보안(API Key & SSL), SQLite DB 설정값을 정의합니다.
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
# 1. 중앙 서버 네트워크 및 HTTPS 설정
# ==========================================
SERVER_HOST = os.getenv("BDS_SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("BDS_SERVER_PORT", "8443"))
BASE_URL = f"https://{SERVER_HOST}:{SERVER_PORT}"

# SSL/TLS 인증서 파일 경로
SSL_CERT_FILE = os.path.join(BASE_DIR, "cert.pem")
SSL_KEY_FILE = os.path.join(BASE_DIR, "key.pem")

# ==========================================
# 2. 클라이언트-서버 공유 API Key 인증 설정
# ==========================================
API_KEY_HEADER_NAME = "access_token"
# 키값은 절대 코드에 하드코딩하지 않고 .env 및 환경변수(os.getenv)에서만 가져옵니다.
SHARED_API_KEY = os.getenv("BDS_API_KEY", "")

# 클라이언트가 HTTP 요청 시 기본으로 포함할 인증 헤더
DEFAULT_HEADERS = {
    API_KEY_HEADER_NAME: SHARED_API_KEY,
    "Content-Type": "application/json",
}

# ==========================================
# 3. WebSocket 양방향 통신 (WSS) 설정
# ==========================================
WS_BASE_URL = f"wss://{SERVER_HOST}:{SERVER_PORT}"
WS_KITCHEN_ENDPOINT = f"{WS_BASE_URL}/ws/kitchen"
WS_APP_ENDPOINT = f"{WS_BASE_URL}/ws/app"

# ==========================================
# 4. 폴링(Polling) 주기 설정 (초 단위, 하위 호환용)
# ==========================================
POLLING_INTERVAL_SEC = 1.5  # 폴링 방식 클라이언트 연동용 주기

# ==========================================
# 5. SQLite 데이터베이스 파일 경로 설정 (Python 기본 내장)
# ==========================================
SQLITE_DB_PATH = os.path.join(BASE_DIR, "kiosk.db")
