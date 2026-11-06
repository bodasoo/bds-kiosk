"""
[1주차 산출물] 공통 환경 설정 및 보안/DB 설정 모듈 (config.py)
- 중앙 서버(server.py)와 4개의 클라이언트(키오스크 1·2, 주방 화면, 고객용 가상 모바일 폰)가
  공통으로 참조하는 네트워크, 보안(API Key & SSL), MySQL DB 설정값을 정의합니다.
"""

import os

# ==========================================
# 1. 중앙 서버 네트워크 및 HTTPS 설정
# ==========================================
SERVER_HOST = os.getenv("BDS_SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("BDS_SERVER_PORT", "8443"))
BASE_URL = f"https://{SERVER_HOST}:{SERVER_PORT}"

# SSL/TLS 인증서 파일 경로 (generate_cert.py 실행 시 생성됨)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SSL_CERT_FILE = os.path.join(BASE_DIR, "cert.pem")
SSL_KEY_FILE = os.path.join(BASE_DIR, "key.pem")

# ==========================================
# 2. 클라이언트-서버 공유 API Key 인증 설정
# ==========================================
API_KEY_HEADER_NAME = "access_token"
SHARED_API_KEY = os.getenv("BDS_API_KEY", "bds-kiosk-secret-token-2026")

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
# 4. MySQL 데이터베이스 연결 설정
# ==========================================
MYSQL_HOST = os.getenv("BDS_DB_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("BDS_DB_PORT", "3306"))
MYSQL_USER = os.getenv("BDS_DB_USER", "root")
MYSQL_PASSWORD = os.getenv("BDS_DB_PASSWORD", "1234")  # 로컬 MySQL 비밀번호에 맞게 변경 가능
MYSQL_DB_NAME = os.getenv("BDS_DB_NAME", "bds_kiosk")
MYSQL_CHARSET = "utf8mb4"

