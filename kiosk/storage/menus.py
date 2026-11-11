from typing import Any, Dict, List
from .connection import get_db_connection

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
