"""클라이언트의 HTTP 경계. UI·SQLite에 의존하지 않는다."""
import requests
import urllib3
from kiosk.config import BASE_URL, DEFAULT_HEADERS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def request_json(method, path, payload=None, *, timeout=8):
    response = requests.request(method, f'{BASE_URL}{path}', json=payload,
                                headers=DEFAULT_HEADERS, verify=False, timeout=timeout)
    response.raise_for_status()
    return response.json()


def server_available():
    try:
        return request_json('GET', '/health', timeout=0.3) == {'status': 'running', 'https': True}
    except (requests.RequestException, ValueError):
        return False
