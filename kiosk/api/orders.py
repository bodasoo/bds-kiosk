from typing import List
import logging
from fastapi import APIRouter, Depends, HTTPException
from .security import verify_api_key
from kiosk.storage.orders import create_order_transaction
from kiosk.schemas import OrderCreateRequest, OrderCreateResponse

router = APIRouter()

@router.post(
    "/order",
    response_model=OrderCreateResponse,
    dependencies=[Depends(verify_api_key)],
)
def create_order(order_req: OrderCreateRequest):
    """[API 2] 키오스크 1·2 신규 주문 생성 (SQLite 트랜잭션 저장)"""
    try:
        result = create_order_transaction(order_req.model_dump())
        return OrderCreateResponse(
            status="OK",
            order_id=result["order_id"],
            order_number=result['order_number'],
            order_source=result['order_source'],
            store_id=result["store_id"],
            store_name=result["store_name"],
            total_price=result["total_price"],
            message="주문이 성공적으로 접수되었습니다.",
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        logging.exception('주문 저장 실패')
        raise HTTPException(status_code=500, detail='주문을 저장하지 못했습니다. 잠시 후 다시 시도해주세요.')
