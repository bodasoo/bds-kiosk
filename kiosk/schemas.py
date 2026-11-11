"""
[1주차 산출물] REST API 요청/응답 데이터 규격 정의 (schemas.py)
- FastAPI 중앙 서버와 4개 클라이언트 간 JSON 통신 페이로드의 무결성을 검증하는 Pydantic 스키마입니다.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class MenuItemSchema(BaseModel):
    """매장별 메뉴 조회 응답 스키마"""
    menu_id: int
    store_id: str
    category: str
    menu_name: str
    price: int


class OrderItemCreate(BaseModel):
    """주문 생성 시 개별 품목 및 매장 특화 옵션 스키마"""
    menu_name: str = Field(..., description="주문 메뉴명 (예: 아메리카노, 참치김밥)")
    price: int = Field(..., ge=0, description="메뉴 단가")
    quantity: int = Field(default=1, ge=1, description="주문 수량")
    # 보다수 커피(KIOSK_01) 전용 옵션: 'HOT' 또는 'ICE' (해당 없을 시 None)
    temperature: Optional[str] = Field(default=None, description="음료 온도 옵션 (HOT / ICE)")
    # 김밥천국(KIOSK_02) 전용 옵션: '당근포함'/'당근제외', '오이포함'/'오이제외'
    exclude_carrot: Optional[str] = Field(default=None, description="당근 옵션 (당근포함 / 당근제외)")
    exclude_cucumber: Optional[str] = Field(default=None, description="오이 옵션 (오이포함 / 오이제외)")


class OrderCreateRequest(BaseModel):
    """[1단계] 키오스크 -> 중앙 서버 주문 생성 요청 (POST /order)"""
    store_id: str = Field(..., description="매장 식별 코드 (KIOSK_01 또는 KIOSK_02)")
    store_name: str = Field(..., description="매장명 (보다수 커피 또는 김밥천국)")
    order_type: str = Field(..., description="매장식사 또는 포장")
    spoon_needed: str = Field(..., description="수저필요함 또는 수저필요없음")
    items: List[OrderItemCreate] = Field(..., min_length=1, description="주문 상세 품목 리스트")


class OrderCreateResponse(BaseModel):
    """주문 생성 완료 응답 스키마"""
    status: str = "OK"
    order_id: int
    order_number: str
    order_source: str
    store_id: str
    store_name: str
    total_price: int
    message: str


class KitchenOrderItemDetail(BaseModel):
    """주방 화면에 표시될 개별 주문 품목 및 옵션"""
    item_id: int
    menu_name: str
    quantity: int
    price: int
    temperature: Optional[str] = None
    exclude_carrot: Optional[str] = None
    exclude_cucumber: Optional[str] = None


class KitchenOrderResponse(BaseModel):
    """[2단계] 주방 화면 폴링 조회 응답 (GET /orders/kitchen)"""
    order_id: int
    order_number: str
    order_source: str
    store_id: str
    store_name: str
    order_type: str
    spoon_needed: str
    total_price: int
    status: str  # PENDING(미접수) 또는 COOKING(조리중)
    order_time: str
    items: List[KitchenOrderItemDetail]


class OrderStatusUpdateResponse(BaseModel):
    """주방 [주문 접수] 및 [조리 완료] 처리 응답"""
    status: str = "OK"
    order_id: int
    new_status: str
    message: str


class MobileNotificationItem(BaseModel):
    """[2·3단계] 고객용 가상 모바일 폰에 전달할 알림 데이터"""
    order_id: int
    store_id: str
    store_name: str
    order_type: str
    total_price: int
    status: str  # COOKING 또는 COMPLETED
    notification_type: str  # ACCEPTED(주문접수/조리시작) 또는 COMPLETED(조리완료/픽업요청)
    summary_text: str
    message: str
    order_time: str
