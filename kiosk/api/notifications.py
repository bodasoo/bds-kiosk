from typing import List
from fastapi import APIRouter, Depends, HTTPException
from .security import verify_api_key
from kiosk.storage.notifications import fetch_and_mark_notifications
from kiosk.schemas import MobileNotificationItem

router = APIRouter()

@router.get(
    "/orders/notifications",
    response_model=List[MobileNotificationItem],
    dependencies=[Depends(verify_api_key)],
)
def get_mobile_notifications():
    """[API 6] 고객용 가상 모바일 폰 1~2초 주기 폴링: 신규 접수/조리완료 알림 조회"""
    return fetch_and_mark_notifications()
