"""DB 정수 식별자와 고객에게 보여주는 주문번호를 구분한다."""


def order_number(order_id, source='KIOSK'):
    return f"{'A' if source == 'APP' else ''}{order_id:03d}"
