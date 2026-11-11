from typing import Any, Dict, List
from .connection import get_db_connection
from kiosk.order_numbers import order_number

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
                   o.notified_completed, o.order_time, o.order_source
            FROM orders o
            JOIN stores s ON o.store_id = s.store_id
            WHERE (o.status = 'COOKING' AND o.notified_accepted = 0)
               OR (o.status = 'COMPLETED' AND o.notified_completed = 0)
            ORDER BY o.order_id ASC;
            """
        )
        rows = [dict(r) for r in cursor.fetchall()]

        for r in rows:
            number = order_number(r['order_id'], r['order_source'])
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
                        "message": f"[주문번호 #{number}] 고객님의 주문이 접수되어 조리가 시작되었습니다!",
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
                        "message": f"[주문번호 #{number}] 조리가 완료되었습니다! 픽업대에서 메뉴를 수령해 주세요.",
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
