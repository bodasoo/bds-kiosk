from typing import List
from fastapi import APIRouter, Depends, HTTPException
from .security import verify_api_key
from kiosk.storage.orders import fetch_kitchen_orders, update_order_status
from kiosk.schemas import KitchenOrderResponse, OrderStatusUpdateResponse

router = APIRouter()

def change_status(order_id, status):
    try:
        return update_order_status(order_id, status)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

@router.get(
    "/orders/kitchen",
    response_model=List[KitchenOrderResponse],
    dependencies=[Depends(verify_api_key)],
)
def get_kitchen_orders():
    """[API 3] 주방 화면 1~2초 주기 폴링: 미접수(PENDING) 및 조리중(COOKING) 주문 목록 조회"""
    return fetch_kitchen_orders()


@router.patch(
    "/orders/{order_id}/accept",
    response_model=OrderStatusUpdateResponse,
    dependencies=[Depends(verify_api_key)],
)
def accept_order(order_id: int):
    """[API 4] 주방 화면 [주문 접수] 버튼 처리 (PENDING -> COOKING)"""
    ok = change_status(order_id, "COOKING")
    if not ok:
        raise HTTPException(status_code=404, detail=f"주문 번호 #{order_id}를 찾을 수 없습니다.")
    return OrderStatusUpdateResponse(
        status="OK",
        order_id=order_id,
        new_status="COOKING",
        message=f"주문 #{order_id} 접수 완료 (조리 시작)",
    )


@router.patch(
    "/orders/{order_id}/complete",
    response_model=OrderStatusUpdateResponse,
    dependencies=[Depends(verify_api_key)],
)
def complete_order(order_id: int):
    """[API 5] 주방 화면 [조리 완료] 버튼 처리 (COOKING -> COMPLETED)"""
    ok = change_status(order_id, "COMPLETED")
    if not ok:
        raise HTTPException(status_code=404, detail=f"주문 번호 #{order_id}를 찾을 수 없습니다.")
    return OrderStatusUpdateResponse(
        status="OK",
        order_id=order_id,
        new_status="COMPLETED",
        message=f"주문 #{order_id} 조리 완료 (고객 픽업 알림 생성)",
    )
