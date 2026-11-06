"""
[1주차 산출물] SQLite 데이터베이스 스키마 구축 및 트랜잭션 관리 모듈 (database.py)
- Python 표준 내장 라이브러리(sqlite3)만을 사용하여 외부 패키지 설치 없이 즉시 동작합니다.
- 4개 정규화 테이블(stores, menus, orders, order_items)을 자동 생성하고,
  보다수 커피(12종) 및 김밥천국(11종) 초기 메뉴 데이터를 자동으로 Seeding합니다.
- 다중 클라이언트 동시 접근 시 WAL(Write-Ahead Logging) 모드와 DB 자체 트랜잭션(ACID)으로
  파이썬 메모리 Lock 없이 데이터 동기화 및 정합성을 보장합니다.
"""

import sqlite3
from typing import Any, Dict, List

from config import SQLITE_DB_PATH

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


def get_db_connection() -> sqlite3.Connection:
    """
    SQLite 데이터베이스 커넥션을 생성하여 반환합니다.
    - row_factory를 sqlite3.Row로 설정하여 딕셔너리 형태로 컬럼에 접근 가능합니다.
    - WAL 모드 및 외래키(Foreign Key) 제약조건을 활성화하여 다중 접속 동시성을 보장합니다.
    """
    conn = sqlite3.connect(SQLITE_DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


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

        conn.commit()
        print(f"[DB] SQLite 데이터베이스('{SQLITE_DB_PATH}') 및 4개 테이블 초기화 완료!")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_menus_by_store(store_id: str) -> List[Dict[str, Any]]:
    """특정 매장(KIOSK_01 또는 KIOSK_02)의 전체 메뉴 목록을 조회합니다."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT menu_id, store_id, category, menu_name, price
            FROM menus
            WHERE store_id = ?
            ORDER BY menu_id ASC;
            """,
            (store_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def create_order_transaction(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    신규 주문을 orders 및 order_items 테이블에 단일 트랜잭션으로 저장합니다.
    다중 키오스크 동시 주문 시 SQLite 트랜잭션이 원자성(Atomicity)과 일관성을 보장합니다.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        items = order_data.get("items", [])
        total_price = sum(int(item["price"]) * int(item.get("quantity", 1)) for item in items)

        # 1. orders 마스터 레코드 생성
        cursor.execute(
            """
            INSERT INTO orders (store_id, order_type, spoon_needed, total_price, status)
            VALUES (?, ?, ?, ?, 'PENDING');
            """,
            (
                order_data["store_id"],
                order_data["order_type"],
                order_data["spoon_needed"],
                total_price,
            ),
        )
        order_id = cursor.lastrowid

        # 2. 각 주문 품목에 대해 menu_id 조회 후 order_items 저장
        for item in items:
            cursor.execute(
                """
                SELECT menu_id FROM menus
                WHERE store_id = ? AND menu_name = ?
                LIMIT 1;
                """,
                (order_data["store_id"], item["menu_name"]),
            )
            menu_row = cursor.fetchone()
            if not menu_row:
                raise ValueError(
                    f"존재하지 않는 메뉴입니다: [{order_data['store_id']}] {item['menu_name']}"
                )
            menu_id = menu_row["menu_id"]

            cursor.execute(
                """
                INSERT INTO order_items (
                    order_id, menu_id, quantity,
                    temperature, exclude_carrot, exclude_cucumber
                )
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    order_id,
                    menu_id,
                    int(item.get("quantity", 1)),
                    item.get("temperature"),
                    item.get("exclude_carrot"),
                    item.get("exclude_cucumber"),
                ),
            )

        conn.commit()
        return {
            "order_id": order_id,
            "store_id": order_data["store_id"],
            "store_name": order_data["store_name"],
            "total_price": total_price,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_kitchen_orders() -> List[Dict[str, Any]]:
    """주방 화면 폴링용: 미접수(PENDING) 및 조리중(COOKING) 주문 목록과 세부 품목을 조회합니다."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT o.order_id, o.store_id, s.store_name, o.order_type,
                   o.spoon_needed, o.total_price, o.status, o.order_time
            FROM orders o
            JOIN stores s ON o.store_id = s.store_id
            WHERE o.status IN ('PENDING', 'COOKING')
            ORDER BY o.order_id ASC;
            """
        )
        orders = [dict(r) for r in cursor.fetchall()]

        for order in orders:
            cursor.execute(
                """
                SELECT oi.item_id, m.menu_name, oi.quantity, m.price,
                       oi.temperature, oi.exclude_carrot, oi.exclude_cucumber
                FROM order_items oi
                JOIN menus m ON oi.menu_id = m.menu_id
                WHERE oi.order_id = ?
                ORDER BY oi.item_id ASC;
                """,
                (order["order_id"],),
            )
            order["items"] = [dict(ir) for ir in cursor.fetchall()]
        return orders
    finally:
        conn.close()


def update_order_status(order_id: int, new_status: str) -> bool:
    """주방 화면에서 [주문 접수](COOKING) 또는 [조리 완료](COMPLETED)로 상태를 변경합니다."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE orders SET status = ? WHERE order_id = ?;",
            (new_status, order_id),
        )
        updated = cursor.rowcount > 0
        conn.commit()
        return updated
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_and_mark_notifications() -> List[Dict[str, Any]]:
    """
    고객용 가상 모바일 폰 폴링용:
    - COOKING 상태이면서 아직 접수 알림(notified_accepted=0)을 보내지 않은 주문
    - COMPLETED 상태이면서 아직 완료 알림(notified_completed=0)을 보내지 않은 주문
    을 조회하고 알림 전송 플래그를 1로 업데이트합니다.
    """
    conn = get_db_connection()
    notifications: List[Dict[str, Any]] = []
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT o.order_id, o.store_id, s.store_name, o.order_type,
                   o.total_price, o.status, o.notified_accepted,
                   o.notified_completed, o.order_time
            FROM orders o
            JOIN stores s ON o.store_id = s.store_id
            WHERE (o.status = 'COOKING' AND o.notified_accepted = 0)
               OR (o.status = 'COMPLETED' AND o.notified_completed = 0)
            ORDER BY o.order_id ASC;
            """
        )
        rows = [dict(r) for r in cursor.fetchall()]

        for r in rows:
            cursor.execute(
                """
                SELECT m.menu_name, oi.quantity
                FROM order_items oi
                JOIN menus m ON oi.menu_id = m.menu_id
                WHERE oi.order_id = ?;
                """,
                (r["order_id"],),
            )
            items = cursor.fetchall()
            summary = ", ".join(f"{it['menu_name']} x{it['quantity']}" for it in items)

            if r["status"] == "COOKING" and r["notified_accepted"] == 0:
                cursor.execute(
                    "UPDATE orders SET notified_accepted = 1 WHERE order_id = ?;",
                    (r["order_id"],),
                )
                notifications.append(
                    {
                        "order_id": r["order_id"],
                        "store_id": r["store_id"],
                        "store_name": r["store_name"],
                        "order_type": r["order_type"],
                        "total_price": r["total_price"],
                        "status": "COOKING",
                        "notification_type": "ACCEPTED",
                        "summary_text": summary,
                        "message": f"[주문번호 #{r['order_id']}] 고객님의 주문이 접수되어 조리가 시작되었습니다!",
                        "order_time": r["order_time"],
                    }
                )
            elif r["status"] == "COMPLETED" and r["notified_completed"] == 0:
                cursor.execute(
                    "UPDATE orders SET notified_completed = 1 WHERE order_id = ?;",
                    (r["order_id"],),
                )
                notifications.append(
                    {
                        "order_id": r["order_id"],
                        "store_id": r["store_id"],
                        "store_name": r["store_name"],
                        "order_type": r["order_type"],
                        "total_price": r["total_price"],
                        "status": "COMPLETED",
                        "notification_type": "COMPLETED",
                        "summary_text": summary,
                        "message": f"[주문번호 #{r['order_id']}] 조리가 완료되었습니다! 픽업대에서 메뉴를 수령해 주세요.",
                        "order_time": r["order_time"],
                    }
                )

        conn.commit()
        return notifications
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    # 초기화된 메뉴 수 확인 출력
    coffee_menus = fetch_menus_by_store("KIOSK_01")
    gimbap_menus = fetch_menus_by_store("KIOSK_02")
    print(f" - 보다수 커피(KIOSK_01) 등록 메뉴: {len(coffee_menus)}종")
    print(f" - 김밥천국(KIOSK_02) 등록 메뉴: {len(gimbap_menus)}종")
