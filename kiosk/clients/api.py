"""클라이언트의 HTTP 경계. UI·SQLite에 의존하지 않는다."""
import requests
from kiosk.config import BASE_URL, DEFAULT_HEADERS, SSL_CA_FILE


def request_json(method, path, payload=None, *, timeout=8):
    response = requests.request(method, f'{BASE_URL}{path}', json=payload,
                                headers=DEFAULT_HEADERS, verify=SSL_CA_FILE, timeout=timeout,
                                allow_redirects=False)
    if 300 <= response.status_code < 400:
        raise requests.RequestException('서버 주소가 변경되었습니다. 접속 설정을 확인해주세요.')
    response.raise_for_status()
    return response.json()


def server_available():
    try:
        return request_json('GET', '/health', timeout=0.3) == {'status': 'running', 'https': True}
    except (requests.RequestException, ValueError, OSError):
        return False
