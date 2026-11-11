"""LAN 시연 인증서와 인증서 다운로드 페이지. 앱과 주방은 같은 서버를 사용한다."""
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import os
from pathlib import Path
import socket
import threading
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

ROOT = Path(__file__).resolve().parents[1]


def lan_address():
    override = os.getenv('BDS_DEMO_IP')
    if override:
        return str(ipaddress.IPv4Address(override))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(('8.8.8.8', 80))
            return sock.getsockname()[0]
        except OSError:
            return socket.gethostbyname(socket.gethostname())


def prepare_certificates(address, directory=None):
    directory = Path(directory or ROOT / '.local' / 'mobile-demo')
    directory.mkdir(parents=True, exist_ok=True)
    ca_key_path, ca_path = directory/'ca-key.pem', directory/'ca.pem'
    now = datetime.now(timezone.utc)
    if ca_key_path.exists() and ca_path.exists():
        ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), None)
        ca = x509.load_pem_x509_certificate(ca_path.read_bytes())
    else:
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'BDS Local Demo CA')])
        ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key())
              .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(days=1))
              .not_valid_after(now+timedelta(days=3650))
              .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
              .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
              .sign(ca_key, hashes.SHA256()))
        ca_key_path.write_bytes(ca_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    (directory/'bds-demo-ca.cer').write_bytes(ca.public_bytes(serialization.Encoding.DER))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, address)]))
            .issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(days=1)).not_valid_after(now+timedelta(days=90))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'), x509.IPAddress(ipaddress.ip_address('127.0.0.1')), x509.IPAddress(ipaddress.ip_address(address))]), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    cert_path, key_path = directory/'server.pem', directory/'server-key.pem'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return cert_path, key_path, directory/'bds-demo-ca.cer'


def run_demo():
    address = lan_address()
    cert, key, ca = prepare_certificates(address)
    url = f'https://{address}:9443/mobile/'
    os.environ.update(BDS_SERVER_HOST='0.0.0.0', BDS_SERVER_PORT='9443',
        BDS_BASE_URL='https://127.0.0.1:9443', BDS_SSL_CERT=str(cert), BDS_SSL_KEY=str(key))
    page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>BDS 로컬 시연 준비</title><body style="font-family:sans-serif;max-width:600px;margin:40px auto;padding:20px;line-height:1.8">
    <h1>BDS 아이폰 시연 준비</h1><ol><li><a href="/bds-demo-ca.cer">시연 인증서 다운로드</a></li>
    <li>설정 → 일반 → VPN 및 기기 관리 → BDS Local Demo CA 프로파일 설치</li>
    <li>설정 → 일반 → 정보 → 인증서 신뢰 설정 → BDS Local Demo CA 전체 신뢰 켜기</li>
    <li><a href="{url}">BDS 픽업 열기</a> → Safari 공유 → 홈 화면에 추가</li>
    <li>홈 화면에서 앱을 열고 앱 설정 → 픽업 푸시 알림 켜기</li></ol>
    <p>PC와 아이폰은 같은 와이파이, 인터넷 연결이 필요합니다. 시연 종료 후 해당 인증서 프로파일을 삭제할 수 있습니다.</p>
    <p>주문 앱: {url}</p></body></html>'''.encode('utf-8')
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/bds-demo-ca.cer':
                content, mime = ca.read_bytes(), 'application/x-x509-ca-cert'
            elif self.path == '/':
                content, mime = page, 'text/html; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        def log_message(self, *args):
            pass
    bootstrap = ThreadingHTTPServer(('0.0.0.0', 9080), Handler)
    threading.Thread(target=bootstrap.serve_forever, daemon=True).start()
    print(f'\n아이폰 Safari에서 준비 페이지: http://{address}:9080/')
    print(f'주문 앱: {url}\n관리자 로그인 후 런처의 주방 종합창을 여세요.\n', flush=True)
    try:
        from kiosk.clients.admin import require_login
        if require_login():
            from kiosk.launcher import run_launcher
            run_launcher()
    finally:
        bootstrap.shutdown()
        bootstrap.server_close()
