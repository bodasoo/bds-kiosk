"""Web Push 키와 발송. DB 작업과 외부 네트워크 요청을 분리한다."""
import base64
import json
import logging
import os
from pathlib import Path
import threading
from urllib.parse import urlsplit
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import webpush, WebPushException
from kiosk.config import VAPID_KEY_FILE, VAPID_SUBJECT
from kiosk.storage.push import claim_pending, record_delivery

_key_lock = threading.Lock()


def public_key():
    path = Path(VAPID_KEY_FILE)
    with _key_lock:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            key = ec.generate_private_key(ec.SECP256R1())
            encoded = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption())
            with path.open('xb') as stream:
                stream.write(encoded)
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    raw = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def decode_key(value):
    return base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)


def validate_subscription(subscription):
    try:
        url = urlsplit(subscription['endpoint'])
        host = url.hostname or ''
        allowed = host == 'fcm.googleapis.com' or any(host.endswith('.' + domain)
            for domain in ('push.apple.com', 'push.services.mozilla.com', 'notify.windows.com'))
        if not (url.scheme == 'https' and allowed and url.port in (None, 443)
                and not url.username and not url.password and not url.fragment):
            raise ValueError()
        keys = subscription['keys']
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), decode_key(keys['p256dh']))
        if len(decode_key(keys['auth'])) != 16:
            raise ValueError()
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError('지원하지 않는 푸시 구독 정보입니다.') from exc


class NoRedirectSession(requests.Session):
    def request(self, *args, **kwargs):
        kwargs['allow_redirects'] = False
        return super().request(*args, **kwargs)


def deliver_one():
    job = claim_pending()
    if not job:
        return False
    try:
        subscription = json.loads(job['subscription_json'])
        validate_subscription(subscription)
        with NoRedirectSession() as session:
            response = webpush(subscription_info=subscription, data=job['payload'],
                vapid_private_key=VAPID_KEY_FILE, vapid_claims={'sub': VAPID_SUBJECT},
                ttl=3600, timeout=10, requests_session=session)
            if response is not None and not 200 <= response.status_code < 300:
                raise ValueError('push HTTP ' + str(response.status_code))
        record_delivery(job)
    except WebPushException as exc:
        status = exc.response.status_code if exc.response is not None else None
        record_delivery(job, error=f'push HTTP {status}', expired=status in (404, 410))
    except Exception as exc:
        record_delivery(job, error=type(exc).__name__)
    return True


def start_push_worker():
    stop = threading.Event()
    if os.getenv('BDS_DISABLE_PUSH_WORKER') == '1':
        return stop, None
    public_key()
    def run():
        while not stop.is_set():
            try:
                worked = deliver_one()
            except Exception:
                logging.exception('푸시 대기열 처리 실패')
                worked = False
            stop.wait(.1 if worked else 2)
    thread = threading.Thread(target=run, daemon=True, name='web-push')
    thread.start()
    return stop, thread
