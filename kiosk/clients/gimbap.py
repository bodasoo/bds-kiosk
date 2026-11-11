from .base import BaseKiosk

STORE_ID = 'KIOSK_02'
STORE_NAME = '김밥천국'


class GimbapKiosk(BaseKiosk):
    def __init__(self):
        super().__init__(STORE_ID, STORE_NAME)
