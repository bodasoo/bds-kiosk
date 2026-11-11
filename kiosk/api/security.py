from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from kiosk.config import API_KEY_HEADER_NAME, SHARED_API_KEY

api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """클라이언트 요청 헤더의 access_token 값을 검증합니다."""
    if not api_key or api_key != SHARED_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="인가되지 않은 클라이언트 접근입니다 (Invalid or missing access_token).",
        )
    return api_key
