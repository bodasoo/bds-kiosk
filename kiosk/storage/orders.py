from typing import Any, Dict, List
from kiosk.order_numbers import order_number
from .connection import get_db_connection


class DuplicateRequestError(ValueError):
    pass


def create_order_transaction(order_data: Dict[str, Any], *, source='KIOSK', customer_hash=None,
                             request_id=None, request_hash=None) -> Dict[str, Any]:
    """키오스크·앱 주문을 같은 트랜잭션과 서버 메뉴 가격으로 저장한다."""
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if request_id:
            previous = conn.execute('SELECT * FROM orders WHERE customer_hash=? AND request_id=?',
                                    (customer_hash, request_id)).fetchone()
            if previous:
                if previous['request_hash'] != request_hash:
                    raise DuplicateRequestError('같은 요청번호로 다른 주문을 전송할 수 없습니다.')
                store = conn.execute('SELECT store_name FROM stores WHERE store_id=?', (previous['store_id'],)).fetchone()
                return dict(order_id=previous['order_id'], order_number=order_number(previous['order_id'], previous['order_source']),
                            order_source=previous['order_source'], store_id=previous['store_id'],
                            store_name=store['store_name'], total_price=previous['total_price'])
        if source == 'APP':
            active = conn.execute("SELECT COUNT(*) FROM orders WHERE customer_hash=? AND status IN ('PENDING','COOKING')", (customer_hash,)).fetchone()[0]
            if active >= 3:
                raise ValueError('진행 중인 주문은 기기당 최대 3건입니다. 기존 주문 완료 후 다시 주문해주세요.')
            total_active = conn.execute("SELECT COUNT(*) FROM orders WHERE order_source='APP' AND status IN ('PENDING','COOKING')").fetchone()[0]
            if total_active >= 200:
                raise ValueError('매장 주문이 많습니다. 잠시 후 다시 주문해주세요.')
        store = conn.execute('SELECT * FROM stores WHERE store_id=?', (order_data['store_id'],)).fetchone()
        if not store:
            raise ValueError('매장을 찾을 수 없습니다.')
        items = order_data.get('items', [])
        if not items or len(items) > 30:
            raise ValueError('주문 품목은 1~30개여야 합니다.')
        resolved = []
        for item in items:
            column = 'menu_id' if item.get('menu_id') is not None else 'menu_name'
            menu = conn.execute(f'SELECT * FROM menus WHERE store_id=? AND {column}=?',
                                (store['store_id'], item[column])).fetchone()
            if not menu:
                raise ValueError('해당 매장에서 주문할 수 없는 메뉴입니다.')
            quantity = int(item.get('quantity', 1))
            if not 1 <= quantity <= 99:
                raise ValueError('수량은 1~99개여야 합니다.')
            resolved.append((menu, quantity, item))
        total_price = sum(menu['price'] * quantity for menu, quantity, _ in resolved)
        cursor = conn.execute('''INSERT INTO orders
            (store_id, order_type, spoon_needed, total_price, status, order_source, customer_hash, request_id, request_hash)
            VALUES (?, ?, ?, ?, 'PENDING', ?, ?, ?, ?)''',
            (store['store_id'], order_data['order_type'], order_data['spoon_needed'], total_price,
             source, customer_hash, request_id, request_hash))
        order_id = cursor.lastrowid
        for menu, quantity, item in resolved:
            conn.execute('''INSERT INTO order_items
                (order_id, menu_id, quantity, temperature, exclude_carrot, exclude_cucumber, unit_price)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (order_id, menu['menu_id'], quantity, item.get('temperature'), item.get('exclude_carrot'),
                 item.get('exclude_cucumber'), menu['price']))
        conn.commit()
        return dict(order_id=order_id, order_number=order_number(order_id, source), order_source=source,
                    store_id=store['store_id'], store_name=store['store_name'], total_price=total_price)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def order_items(conn, order_id):
    return [dict(row) for row in conn.execute('''SELECT oi.item_id, oi.menu_id, m.menu_name,
        oi.quantity, COALESCE(oi.unit_price, m.price) AS price,
        oi.temperature, oi.exclude_carrot, oi.exclude_cucumber
        FROM order_items oi JOIN menus m ON oi.menu_id=m.menu_id WHERE oi.order_id=?
        ORDER BY oi.item_id''', (order_id,))]


def serialize_order(conn, row):
    order = dict(row)
    order['order_number'] = order_number(order['order_id'], order['order_source'])
    order['items'] = order_items(conn, order['order_id'])
    return order


def fetch_kitchen_orders() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.execute('''SELECT o.order_id, o.store_id, s.store_name, o.order_type,
            o.spoon_needed, o.total_price, o.status, o.order_time, o.order_source
            FROM orders o JOIN stores s ON o.store_id=s.store_id
            WHERE o.status IN ('PENDING', 'COOKING') ORDER BY o.order_id''')
        return [serialize_order(conn, row) for row in rows]
    finally:
        conn.close()


def update_order_status(order_id: int, new_status: str) -> bool:
    from .push import enqueue_order_notification
    expected = {'COOKING': 'PENDING', 'COMPLETED': 'COOKING'}
    if new_status not in expected:
        raise ValueError('지원하지 않는 주문 상태입니다.')
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        order = conn.execute('SELECT * FROM orders WHERE order_id=?', (order_id,)).fetchone()
        if not order:
            return False
        if order['status'] == new_status:
            return True
        if order['status'] != expected[new_status]:
            raise ValueError('주문 상태가 변경되었습니다. 목록을 새로고침해주세요.')
        conn.execute('UPDATE orders SET status=? WHERE order_id=?', (new_status, order_id))
        enqueue_order_notification(conn, order_id, new_status)
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
