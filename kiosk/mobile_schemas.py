from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class MobileItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    menu_id: int
    quantity: int = Field(default=1, ge=1, le=99)
    temperature: Literal['HOT', 'ICE'] | None = None
    exclude_carrot: Literal['당근포함', '당근제외'] | None = None
    exclude_cucumber: Literal['오이포함', '오이제외'] | None = None


class MobileOrder(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    store_id: Literal['KIOSK_01', 'KIOSK_02']
    spoon_needed: Literal['수저필요함', '수저필요없음'] = '수저필요없음'
    items: list[MobileItem] = Field(min_length=1, max_length=30)


class PushKeys(BaseModel):
    p256dh: str = Field(max_length=100)
    auth: str = Field(max_length=30)


class PushSubscription(BaseModel):
    endpoint: str = Field(max_length=2048)
    keys: PushKeys
