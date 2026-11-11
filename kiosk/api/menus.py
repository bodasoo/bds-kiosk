from typing import List
from fastapi import APIRouter, Depends, HTTPException
from .security import verify_api_key
from kiosk.storage.menus import fetch_menus_by_store
from kiosk.schemas import MenuItemSchema

router = APIRouter()

@router.get(
    "/menus/{store_id}",
    response_model=List[MenuItemSchema],
    dependencies=[Depends(verify_api_key)],
)
def get_store_menus(store_id: str):
    """[API 1] 매장별(KIOSK_01 / KIOSK_02) 전체 메뉴 조회"""
    return fetch_menus_by_store(store_id)
