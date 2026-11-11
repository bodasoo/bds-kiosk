"""
[1주차 산출물] HTTPS (SSL/TLS) 자체 서명 인증서 생성 스크립트 (generate_cert.py)
- Uvicorn 중앙 서버(server.py)와 클라이언트 간 전송 구간 암호화를 위해
  로컬 개발/시연용 개인키(key.pem)와 공개키 인증서(cert.pem)를 생성합니다.
"""

import datetime
import ipaddress
import os
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from kiosk.config import SSL_CERT_FILE, SSL_KEY_FILE


def generate_self_signed_cert(cert_path: str = SSL_CERT_FILE, key_path: str = SSL_KEY_FILE, *, force=False) -> None:
    """RSA 2048비트 개인키 및 자체 서명 X.509 SSL 인증서(cert.pem, key.pem) 생성"""
    if not force and os.path.exists(cert_path) and os.path.exists(key_path):
        print(f"[SSL] 기존 인증서 파일이 존재합니다: {cert_path}, {key_path}")
        return

    print("[SSL] 새로운 자체 서명 SSL/TLS 인증서를 생성합니다...")

    # 1. RSA 2048-bit 개인키 생성
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # 2. 인증서 주체(Subject) 및 발급자(Issuer) 설정
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "KR"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Gwangju"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Bodasu Kiosk System"),
            x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1"),
        ]
    )

    now = datetime.datetime.now(datetime.timezone.utc)

    # 3. X.509 인증서 빌드 (localhost 및 127.0.0.1 SAN 포함)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()), critical=False)
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # 4. key.pem 저장
    with open(key_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # 5. cert.pem 저장
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"[SSL] 인증서 생성 완료!\n - 인증서: {cert_path}\n - 개인키: {key_path}")


if __name__ == "__main__":
    generate_self_signed_cert()
