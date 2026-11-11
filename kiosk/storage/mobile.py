from .connection import get_db_connection
from .orders import serialize_order


def catalog():
    conn = get_db_connection()
    try:
        stores = [dict(row) for row in conn.execute('SELECT store_id, store_name FROM stores ORDER BY store_id')]
        for store in stores:
            store['menus'] = [dict(row) for row in conn.execute('SELECT * FROM menus WHERE store_id=? ORDER BY menu_id', (store['store_id'],))]
        return stores
    finally:
        conn.close()


def customer_orders(customer_hash):
    conn = get_db_connection()
    try:
        rows = conn.execute('''SELECT o.order_id, o.store_id, s.store_name, o.order_type,
            o.spoon_needed, o.total_price, o.status, o.order_time, o.order_source
            FROM orders o JOIN stores s ON o.store_id=s.store_id WHERE o.customer_hash=?
            ORDER BY o.order_id DESC LIMIT 30''', (customer_hash,))
        return [serialize_order(conn, row) for row in rows]
    finally:
        conn.close()
