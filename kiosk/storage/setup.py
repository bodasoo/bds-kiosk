from kiosk.config import SQLITE_DB_PATH
from .connection import get_db_connection
from .seed import INITIAL_STORES, INITIAL_MENUS
from .migrations import migrate_mobile

def init_db() -> None:
    """
    SQLite 데이터베이스(kiosk.db) 및 4개 핵심 테이블을 생성하고,
    초기 매장(2곳)과 메뉴(23종) 데이터를 적재(Seeding)합니다.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # (1) stores 테이블
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stores (
                store_id TEXT PRIMARY KEY,
                store_name TEXT NOT NULL,
                device_ip TEXT DEFAULT '127.0.0.1'
            );
            """
        )

        # (2) menus 테이블
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS menus (
                menu_id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id TEXT NOT NULL,
                category TEXT NOT NULL,
                menu_name TEXT NOT NULL,
                price INTEGER NOT NULL,
                FOREIGN KEY (store_id) REFERENCES stores(store_id)
                    ON DELETE CASCADE ON UPDATE CASCADE
            );
            """
        )

        # (3) orders 테이블 (주문 상태 및 모바일 알림 수신 여부 포함)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id TEXT NOT NULL,
                order_type TEXT NOT NULL,
                spoon_needed TEXT NOT NULL,
                total_price INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                notified_accepted INTEGER NOT NULL DEFAULT 0,
                notified_completed INTEGER NOT NULL DEFAULT 0,
                order_time DATETIME NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (store_id) REFERENCES stores(store_id)
                    ON DELETE RESTRICT ON UPDATE CASCADE
            );
            """
        )

        # (4) order_items 테이블 (매장별 세부 옵션 포함)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                menu_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                temperature TEXT NULL,
                exclude_carrot TEXT NULL,
                exclude_cucumber TEXT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
                    ON DELETE CASCADE ON UPDATE CASCADE,
                FOREIGN KEY (menu_id) REFERENCES menus(menu_id)
                    ON DELETE RESTRICT ON UPDATE CASCADE
            );
            """
        )

        # 초기 매장 데이터 적재 (INSERT OR IGNORE로 중복 방지)
        cursor.executemany(
            """
            INSERT OR IGNORE INTO stores (store_id, store_name, device_ip)
            VALUES (?, ?, ?);
            """,
            INITIAL_STORES,
        )

        # 초기 메뉴 데이터 적재 (비어 있을 때만 적재)
        cursor.execute("SELECT COUNT(*) AS cnt FROM menus;")
        row = cursor.fetchone()
        if row and row["cnt"] == 0:
            cursor.executemany(
                """
                INSERT INTO menus (store_id, category, menu_name, price)
                VALUES (?, ?, ?, ?);
                """,
                INITIAL_MENUS,
            )
            print(f"[DB] 초기 메뉴 {len(INITIAL_MENUS)}종 시드 데이터 적재 완료.")

        migrate_mobile(conn)
        conn.commit()
        print(f"[DB] SQLite 데이터베이스('{SQLITE_DB_PATH}') 및 4개 테이블 초기화 완료!")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
