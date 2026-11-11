"""푸시 구독과 발송 대기열. 주문 상태 변경과 알림 적재는 한 트랜잭션이다."""
import json
import time
from kiosk.order_numbers import order_number
from .connection import get_db_connection


def enqueue_order_notification(conn, order_id, state, endpoint=None):
    row = conn.execute('''SELECT o.*, s.store_name FROM orders o
        JOIN stores s ON o.store_id=s.store_id WHERE order_id=?''', (order_id,)).fetchone()
    if not row or row['order_source'] != 'APP':
        return
    number = order_number(order_id, 'APP')
    payload = json.dumps(dict(title=f'{number} · ' + ('픽업 준비 완료' if state == 'COMPLETED' else '조리를 시작했어요'),
        body=f"{row['store_name']}에서 " + ('주문하신 메뉴를 받아가세요.' if state == 'COMPLETED' else '메뉴를 준비하고 있어요.'),
        url='/mobile/#orders', tag=f'order-{order_id}-{state}', order_number=number), ensure_ascii=False)
    query = 'SELECT endpoint FROM push_subscriptions WHERE customer_hash=?'
    parameters = [row['customer_hash']]
    if endpoint:
        query += ' AND endpoint=?'
        parameters.append(endpoint)
    for subscription in conn.execute(query, parameters):
        conn.execute('''INSERT OR IGNORE INTO push_outbox(order_id, state, endpoint, payload)
            VALUES (?, ?, ?, ?)''', (order_id, state, subscription['endpoint'], payload))


def save_subscription(customer_hash, subscription):
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        endpoint = subscription['endpoint']
        existing = conn.execute('SELECT customer_hash FROM push_subscriptions WHERE endpoint=?', (endpoint,)).fetchone()
        if existing and existing['customer_hash'] != customer_hash:
            raise ValueError('이 알림 구독은 다른 주문 세션에 연결되어 있습니다. 알림을 다시 등록해주세요.')
        if not existing:
            count = conn.execute('SELECT COUNT(*) FROM push_subscriptions WHERE customer_hash=?', (customer_hash,)).fetchone()[0]
            total = conn.execute('SELECT COUNT(*) FROM push_subscriptions').fetchone()[0]
            if count >= 3 or total >= 300:
                raise ValueError('알림 등록 한도에 도달했습니다. 기존 구독을 해제한 뒤 다시 시도해주세요.')
        conn.execute('''INSERT INTO push_subscriptions VALUES (?, ?, ?, ?)
            ON CONFLICT(endpoint) DO UPDATE SET subscription_json=excluded.subscription_json''',
            (endpoint, customer_hash, json.dumps(subscription), time.time()))
        rows = conn.execute('''SELECT order_id, status FROM orders WHERE customer_hash=?
            AND status IN ('COOKING', 'COMPLETED')
            AND order_time >= datetime('now', 'localtime', '-1 day')''', (customer_hash,)).fetchall()
        for row in rows:
            enqueue_order_notification(conn, row['order_id'], row['status'], endpoint)
        conn.commit()
    finally:
        conn.close()


def remove_subscriptions(customer_hash):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM push_subscriptions WHERE customer_hash=?', (customer_hash,))
        conn.commit()
    finally:
        conn.close()


def claim_pending():
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('''SELECT p.*, s.subscription_json FROM push_outbox p
            JOIN push_subscriptions s ON s.endpoint=p.endpoint
            WHERE p.sent_at IS NULL AND p.attempts < 8 AND p.next_attempt <= ?
            ORDER BY p.id LIMIT 1''', (time.time(),)).fetchone()
        if row:
            conn.execute('UPDATE push_outbox SET attempts=attempts+1, next_attempt=? WHERE id=?', (time.time()+60, row['id']))
        conn.commit()
        return dict(row) if row else None
    finally:
        conn.close()


def record_delivery(job, error=None, expired=False):
    conn = get_db_connection()
    try:
        if expired:
            conn.execute('DELETE FROM push_subscriptions WHERE endpoint=?', (job['endpoint'],))
        elif error:
            delay = min(300, 5 * 2 ** job['attempts'])
            conn.execute('UPDATE push_outbox SET next_attempt=?, last_error=? WHERE id=?', (time.time()+delay, error[:100], job['id']))
        else:
            conn.execute('UPDATE push_outbox SET sent_at=?, last_error=NULL WHERE id=?', (time.time(), job['id']))
        conn.commit()
    finally:
        conn.close()
