# backend/middleware/api_key_auth.py
from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader
from services.api_key_service import APIKeyService
from typing import Dict

# API Key header name
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    request: Request,
    api_key: str = Security(API_KEY_HEADER)
) -> Dict:
    """
    FastAPI dependency that:
    1. Extracts X-API-Key from header
    2. Validates it against Firestore
    3. Returns tenant info dict
    4. Stores tenant info in request.state for downstream use
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "missing_api_key",
                "message": "X-API-Key header is required. "
                           "Register at /v1/tenants/register to get your API key."
            }
        )

    tenant_info = await APIKeyService.validate_key(api_key)

    if not tenant_info:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_api_key",
                "message": "Invalid or revoked API key. "
                           "Contact support or rotate your key."
            }
        )

    # Store tenant info in request state for downstream use
    request.state.tenant = tenant_info
    return tenant_info