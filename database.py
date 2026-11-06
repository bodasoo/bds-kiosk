"""
[1주차 산출물] MySQL 데이터베이스 스키마 구축 및 트랜잭션 관리 모듈 (database.py)
- 4개 정규화 테이블(stores, menus, orders, order_items)을 자동 생성하고,
  보다수 커피(12종) 및 김밥천국(11종) 초기 메뉴 데이터를 자동으로 Seeding합니다.
- 다중 클라이언트 동시 접근 시 파이썬 메모리 Lock 대신 MySQL InnoDB 트랜잭션(ACID)으로
  데이터 동기화 및 정합성을 보장합니다.
"""

from typing import Any, Dict, List
import pymysql
from pymysql.cursors import DictCursor

from config import (
    MYSQL_CHARSET,
    MYSQL_DB_NAME,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
)
from schemas import OrderCreateRequest


# ==========================================
# 초기 매장 및 메뉴 시드(Seed) 데이터 정의 (총 23종)
# ==========================================
INITIAL_STORES = [
    ("KIOSK_01", "보다수 커피", "127.0.0.1"),
    ("KIOSK_02", "김밥천국", "127.0.0.1"),
]

INITIAL_MENUS = [
    # 1) 보다수 커피 (KIOSK_01) - 12종
    ("KIOSK_01", "커피", "아메리카노", 3000),
    ("KIOSK_01", "커피", "카페라떼", 3500),
    ("KIOSK_01", "커피", "바닐라라떼", 4000),
    ("KIOSK_01", "커피", "헤이즐럿라떼", 4000),
    ("KIOSK_01", "커피", "돌체라떼", 4500),
    ("KIOSK_01", "스무디", "플레인 요거트 스무디", 4500),
    ("KIOSK_01", "스무디", "딸기 요거트 스무디", 4800),
    ("KIOSK_01", "차/기타", "아이스티", 3000),
    ("KIOSK_01", "차/기타", "레몬차", 4000),
    ("KIOSK_01", "차/기타", "자몽차", 4000),
    ("KIOSK_01", "차/기타", "유자차", 4000),
    ("KIOSK_01", "차/기타", "쌍화탕", 4500),
    # 2) 김밥천국 (KIOSK_02) - 11종
    ("KIOSK_02", "김밥류", "기본 김밥", 3000),
    ("KIOSK_02", "김밥류", "참치김밥", 4000),
    ("KIOSK_02", "김밥류", "치즈김밥", 4000),
    ("KIOSK_02", "김밥류", "돈가스 김밥", 4500),
    ("KIOSK_02", "김밥류", "야채 김밥", 3500),
    ("KIOSK_02", "김밥류", "땡초김밥", 4000),
    ("KIOSK_02", "김밥류", "제육김밥", 4500),
    ("KIOSK_02", "식사/분식류", "돈가스", 8000),
    ("KIOSK_02", "식사/분식류", "라면", 4000),
    ("KIOSK_02", "식사/분식류", "우동", 5000),
    ("KIOSK_02", "식사/분식류", "떡볶이", 4500),
]


def get_db_connection(include_db: bool = True) -> pymysql.connections.Connection:
    """MySQL 데이터베이스 커넥션을 생성하여 반환합니다."""
    conn_kwargs: Dict[str, Any] = {
        "host": MYSQL_HOST,
        "port": MYSQL_PORT,
        "user": MYSQL_USER,
        "password": MYSQL_PASSWORD,
        "charset": MYSQL_CHARSET,
        "cursorclass": DictCursor,
        "autocommit": False,  # 명시적 트랜잭션(COMMIT/ROLLBACK) 사용
    }
    if include_db:
        conn_kwargs["database"] = MYSQL_DB_NAME
    return pymysql.connect(**conn_kwargs)


def init_db() -> None:
    """
    데이터베이스(bds_kiosk) 및 4개 핵심 테이블을 생성하고,
    초기 매장(2곳)과 메뉴(23종) 데이터를 적재(Seeding)합니다.
    """
    # 1. 데이터베이스가 없으면 먼저 생성
    root_conn = get_db_connection(include_db=False)
    try:
        with root_conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DB_NAME}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
        root_conn.commit()
    finally:
        root_conn.close()

    # 2. 테이블 4종 생성 및 초기 데이터 Seeding
    conn = get_db_connection(include_db=True)
    try:
        with conn.cursor() as cursor:
            # (1) stores 테이블
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS stores (
                    store_id VARCHAR(20) PRIMARY KEY,
                    store_name VARCHAR(50) NOT NULL,
                    device_ip VARCHAR(45) DEFAULT '127.0.0.1'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # (2) menus 테이블
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS menus (
                    menu_id INT AUTO_INCREMENT PRIMARY KEY,
                    store_id VARCHAR(20) NOT NULL,
                    category VARCHAR(30) NOT NULL,
                    menu_name VARCHAR(50) NOT NULL,
                    price INT NOT NULL,
                    CONSTRAINT fk_menus_store
                        FOREIGN KEY (store_id) REFERENCES stores(store_id)
                        ON DELETE CASCADE ON UPDATE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # (3) orders 테이블 (주문 상태 및 모바일 알림 수신 여부 포함)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    order_id INT AUTO_INCREMENT PRIMARY KEY,
                    store_id VARCHAR(20) NOT NULL,
                    order_type VARCHAR(20) NOT NULL,
                    spoon_needed VARCHAR(20) NOT NULL,
                    total_price INT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
                    notified_accepted TINYINT(1) NOT NULL DEFAULT 0,
                    notified_completed TINYINT(1) NOT NULL DEFAULT 0,
                    order_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_orders_store
                        FOREIGN KEY (store_id) REFERENCES stores(store_id)
                        ON DELETE RESTRICT ON UPDATE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # (4) order_items 테이블 (매장별 세부 옵션 포함)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS order_items (
                    item_id INT AUTO_INCREMENT PRIMARY KEY,
                    order_id INT NOT NULL,
                    menu_id INT NOT NULL,
                    quantity INT NOT NULL DEFAULT 1,
                    temperature VARCHAR(10) NULL,
                    exclude_carrot VARCHAR(20) NULL,
                    exclude_cucumber VARCHAR(20) NULL,
                    CONSTRAINT fk_items_order
                        FOREIGN KEY (order_id) REFERENCES orders(order_id)
                        ON DELETE CASCADE ON UPDATE CASCADE,
                    CONSTRAINT fk_items_menu
                        FOREIGN KEY (menu_id) REFERENCES menus(menu_id)
                        ON DELETE RESTRICT ON UPDATE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )

            # 초기 매장 데이터 적재 (IGNORE로 중복 방지)
            cursor.executemany(
                """
                INSERT IGNORE INTO stores (store_id, store_name, device_ip)
                VALUES (%s, %s, %s);
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
                    VALUES (%s, %s, %s, %s);
                    """,
                    INITIAL_MENUS,
                )
                print(f"[DB] 초기 메뉴 {len(INITIAL_MENUS)}종 시드 데이터 적재 완료.")

        conn.commit()
        print(f"[DB] MySQL '{MYSQL_DB_NAME}' 데이터베이스 및 4개 테이블 초기화 완료.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_menus_by_store(store_id: str) -> List[Dict[str, Any]]:
    """특정 매장(KIOSK_01 또는 KIOSK_02)의 전체 메뉴 목록을 조회합니다."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT menu_id, store_id, category, menu_name, price
                FROM menus
                WHERE store_id = %s
                ORDER BY menu_id ASC;
                """,
                (store_id,),
            )
            return list(cursor.fetchall())
    finally:
        conn.close()


def create_order_transaction(order_req: OrderCreateRequest) -> Dict[str, Any]:
    """
    신규 주문을 orders 및 order_items 테이블에 단일 트랜잭션으로 저장합니다.
    다중 키오스크 동시 주문 시 MySQL 트랜잭션이 원자성(Atomicity)과 일관성을 보장합니다.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            total_price = sum(item.price * item.quantity for item in order_req.items)

            # 1. orders 마스터 레코드 생성
            cursor.execute(
                """
                INSERT INTO orders (store_id, order_type, spoon_needed, total_price, status)
                VALUES (%s, %s, %s, %s, 'PENDING');
                """,
                (
                    order_req.store_id,
                    order_req.order_type,
                    order_req.spoon_needed,
                    total_price,
                ),
            )
            order_id = cursor.lastrowid

            # 2. 각 주문 품목에 대해 menu_id 조회 후 order_items 저장
            for item in order_req.items:
                cursor.execute(
                    """
                    SELECT menu_id FROM menus
                    WHERE store_id = %s AND menu_name = %s
                    LIMIT 1;
                    """,
                    (order_req.store_id, item.menu_name),
                )
                menu_row = cursor.fetchone()
                if not menu_row:
                    raise ValueError(
                        f"존재하지 않는 메뉴입니다: [{order_req.store_id}] {item.menu_name}"
                    )
                menu_id = menu_row["menu_id"]

                cursor.execute(
                    """
                    INSERT INTO order_items (
                        order_id, menu_id, quantity,
                        temperature, exclude_carrot, exclude_cucumber
                    )
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (
                        order_id,
                        menu_id,
                        item.quantity,
                        item.temperature,
                        item.exclude_carrot,
                        item.exclude_cucumber,
                    ),
                )

        conn.commit()
        return {
            "order_id": order_id,
            "store_id": order_req.store_id,
            "store_name": order_req.store_name,
            "total_price": total_price,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()

