"""모바일 주문 추가용 비파괴·재실행 가능 마이그레이션."""


def migrate_mobile(conn):
    order_columns = {row['name'] for row in conn.execute('PRAGMA table_info(orders)')}
    for name, definition in {
        'order_source': "TEXT NOT NULL DEFAULT 'KIOSK'",
        'customer_hash': 'TEXT', 'request_id': 'TEXT', 'request_hash': 'TEXT',
    }.items():
        if name not in order_columns:
            conn.execute(f'ALTER TABLE orders ADD COLUMN {name} {definition}')
    item_columns = {row['name'] for row in conn.execute('PRAGMA table_info(order_items)')}
    if 'unit_price' not in item_columns:
        conn.execute('ALTER TABLE order_items ADD COLUMN unit_price INTEGER')
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS mobile_order_request ON orders(customer_hash, request_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS mobile_customer_orders ON orders(customer_hash, order_id)')
    conn.execute('''CREATE TABLE IF NOT EXISTS push_subscriptions (
        endpoint TEXT PRIMARY KEY, customer_hash TEXT NOT NULL,
        subscription_json TEXT NOT NULL, created_at REAL NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS push_outbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL,
        state TEXT NOT NULL, endpoint TEXT NOT NULL, payload TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
        sent_at REAL, last_error TEXT,
        UNIQUE(order_id, state, endpoint),
        FOREIGN KEY(order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
        FOREIGN KEY(endpoint) REFERENCES push_subscriptions(endpoint) ON DELETE CASCADE)''')
