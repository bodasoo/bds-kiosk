"""
[1주차 산출물] 공통 환경 설정 및 보안/DB 설정 모듈 (config.py)
- 중앙 서버(server.py)와 4개의 클라이언트(키오스크 1·2, 주방 화면, 고객용 가상 모바일 폰)가
  공통으로 참조하는 네트워크, 보안(API Key & SSL), SQLite DB 설정값을 정의합니다.
"""

import os
import secrets

# 프로젝트 기본 경로
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# .env 파일 자동 로드 (키값 노출 방지 및 환경변수 주입)
ENV_FILE = os.path.join(BASE_DIR, ".env")
if not os.getenv('BDS_API_KEY') and not os.path.exists(ENV_FILE):
    try:
        with open(ENV_FILE, 'x', encoding='utf-8') as stream:
            stream.write('BDS_API_KEY=' + secrets.token_urlsafe(32) + '\n')
    except FileExistsError:
        pass
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
BASE_URL = os.getenv('BDS_BASE_URL', f"https://{'127.0.0.1' if SERVER_HOST == '0.0.0.0' else SERVER_HOST}:{SERVER_PORT}")

# SSL/TLS 인증서 파일 경로
SSL_CERT_FILE = os.getenv('BDS_SSL_CERT', os.path.join(BASE_DIR, "cert.pem"))
SSL_KEY_FILE = os.getenv('BDS_SSL_KEY', os.path.join(BASE_DIR, "key.pem"))
SSL_CA_FILE = os.getenv('BDS_SSL_CA', SSL_CERT_FILE)

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
# 3. 폴링(Polling) 주기 설정 (초 단위)
# ==========================================
POLLING_INTERVAL_SEC = 1.5  # 주방 화면 및 고객용 가상 모바일 폰 폴링 간격 (1~2초)

# ==========================================
# 4. SQLite 데이터베이스 파일 경로 설정 (Python 기본 내장)
# ==========================================
SQLITE_DB_PATH = os.getenv('BDS_DB_PATH', os.path.join(BASE_DIR, "kiosk.db"))

# 로컬 관리자 화면의 비밀번호 해시 전용 파일
ADMIN_ENV_FILE = os.path.join(BASE_DIR, ".env.admin")

VAPID_KEY_FILE = os.getenv('BDS_VAPID_KEY_FILE', os.path.join(BASE_DIR, '.local', 'vapid.pem'))
VAPID_SUBJECT = os.getenv('BDS_VAPID_SUBJECT', 'mailto:admin@example.com')
