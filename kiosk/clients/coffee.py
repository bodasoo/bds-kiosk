from .base import BaseKiosk

STORE_ID = 'KIOSK_01'
STORE_NAME = '보다수 커피'


class BodasuCoffeeKiosk(BaseKiosk):
    def __init__(self):
        super().__init__(STORE_ID, STORE_NAME)
