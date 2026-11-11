import hashlib
import json
import re
import time
import threading
from collections import deque
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from kiosk.mobile_schemas import MobileOrder, PushSubscription
from kiosk.storage.mobile import catalog, customer_orders
from kiosk.storage.orders import create_order_transaction, DuplicateRequestError
from kiosk.storage.push import save_subscription, remove_subscriptions
from kiosk.push import public_key, validate_subscription

router = APIRouter(prefix='/api/mobile')
_write_times = {}
_write_lock = threading.Lock()


def limit_writes(request: Request):
    # 로컬 단일 서버용. 외부 프록시 헤더를 신뢰하지 않고 실제 접속 IP로 제한한다.
    address = request.client.host if request.client else 'unknown'
    now = time.monotonic()
    with _write_lock:
        for key in list(_write_times):
            if _write_times[key][-1] <= now - 60:
                del _write_times[key]
        if address not in _write_times and len(_write_times) >= 1024:
            raise HTTPException(429, '요청이 많습니다. 1분 후 다시 시도해주세요.', headers={'Retry-After':'60'})
        times = _write_times.setdefault(address, deque())
        while times and times[0] <= now - 60:
            times.popleft()
        if len(times) >= 20:
            raise HTTPException(429, '요청이 많습니다. 1분 후 다시 시도해주세요.', headers={'Retry-After':'60'})
        times.append(now)


def customer(x_customer_token: str = Header(default='')):
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', x_customer_token):
        raise HTTPException(401, '이 기기의 주문 식별자가 필요합니다.')
    return hashlib.sha256(x_customer_token.encode()).hexdigest()


@router.get('/catalog')
def get_catalog():
    return catalog()


@router.get('/orders')
def get_orders(owner=Depends(customer)):
    return customer_orders(owner)


@router.post('/orders', dependencies=[Depends(limit_writes)])
def order(request: MobileOrder, owner=Depends(customer)):
    data = request.model_dump(mode='json')
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    data['order_type'] = '포장'
    try:
        return create_order_transaction(data, source='APP', customer_hash=owner,
            request_id=str(request.request_id), request_hash=digest)
    except DuplicateRequestError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get('/push/config')
def push_config():
    return {'public_key': public_key()}


@router.post('/push/subscriptions', dependencies=[Depends(limit_writes)])
def subscribe(subscription: PushSubscription, owner=Depends(customer)):
    data = subscription.model_dump()
    try:
        validate_subscription(data)
        save_subscription(owner, data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {'status': 'OK'}


@router.delete('/push/subscriptions')
def unsubscribe(owner=Depends(customer)):
    remove_subscriptions(owner)
    return {'status': 'OK'}
