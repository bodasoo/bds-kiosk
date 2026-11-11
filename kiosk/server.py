import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from kiosk.config import BASE_DIR
from kiosk.push import start_push_worker
from kiosk.config import SERVER_HOST, SERVER_PORT, SSL_CERT_FILE, SSL_KEY_FILE
from kiosk.certificates import generate_self_signed_cert
from kiosk.storage.setup import init_db
from kiosk.api import menus, orders, kitchen, notifications, mobile

app = FastAPI(
    title="🛒 멀티 클라이언트 키오스크 및 주방/고객 연동 중앙 서버",
    description="HTTPS(SSL/TLS) 및 API Key(access_token) 인증 기반 중앙 주문/조리/알림 관리 API",
    version="1.0.0",
)

@app.on_event("startup")
def on_startup() -> None:
    """서버 시작 시 SQLite DB 및 23종 초기 메뉴 자동 초기화"""
    init_db()
    app.state.push_stop, app.state.push_thread = start_push_worker()


@app.on_event('shutdown')
def on_shutdown():
    app.state.push_stop.set()
    if app.state.push_thread:
        app.state.push_thread.join(timeout=12)

@app.get("/health")
def health_check() -> dict:
    """서버 동작 상태 확인 엔드포인트"""
    return {"status": "running", "https": True}

for module in (menus, orders, kitchen, notifications, mobile):
    app.include_router(module.router)

app.mount('/mobile', StaticFiles(directory=os.path.join(BASE_DIR, 'mobile'), html=True), name='mobile')

def run_server() -> None:
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
