# backend/routers/tenant.py
"""
Tenant management router — registration, info, key rotation.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from models.schemas import (
    TenantRegisterRequest, TenantRegisterResponse,
    TenantInfo, APIKeyRotateResponse
)
from services.api_key_service import APIKeyService
from services.tenant_service import TenantService
from middleware.api_key_auth import verify_api_key
from config.settings import settings

router = APIRouter(prefix="/v1/tenants", tags=["Tenant Management"])


@router.post("/register", response_model=TenantRegisterResponse)
async def register_tenant(req: TenantRegisterRequest):
    """
    Register a new company/tenant and receive an API key.
    
    ⚠️ The API key is shown ONLY ONCE. Save it securely.
    """
    # Verify admin secret
    if req.admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(
            status_code=403,
            detail="Invalid admin secret. Contact the platform administrator."
        )

    try:
        # Create tenant and API key
        tenant_id, raw_api_key = await APIKeyService.create_key(
            company_name=req.company_name,
            email=req.email,
            tier=req.tier.value,
            webhook_url=req.webhook_url
        )

        # Get rate limit for tier
        from config.settings import TenantTier
        rate_limit = settings.RATE_LIMITS.get(TenantTier(req.tier.value), 100)

        return TenantRegisterResponse(
            tenant_id=tenant_id,
            company_name=req.company_name,
            api_key=raw_api_key,
            tier=req.tier,
            rate_limit=rate_limit,
            message="🔑 Save your API key now — it won't be shown again! "
                    "Use it in the X-API-Key header for all API calls."
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.get("/me", response_model=TenantInfo)
async def get_my_tenant(
    tenant: dict = Depends(verify_api_key)
):
    """Get your tenant info (requires API key)"""
    tenant_data = await TenantService.get_tenant(tenant["tenant_id"])

    if not tenant_data:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return TenantInfo(
        tenant_id=tenant_data["tenant_id"],
        company_name=tenant_data["company_name"],
        email=tenant_data["email"],
        tier=tenant_data.get("tier", "free"),
        created_at=tenant_data.get("created_at", ""),
        is_active=tenant_data.get("is_active", True),
        webhook_url=tenant_data.get("webhook_url"),
        total_api_calls=tenant_data.get("total_api_calls", 0)
    )


@router.post("/rotate-key", response_model=APIKeyRotateResponse)
async def rotate_api_key(
    tenant: dict = Depends(verify_api_key)
):
    """
    Rotate your API key. The old key is revoked immediately.
    
    ⚠️ The new key is shown ONLY ONCE.
    """
    try:
        new_key = await APIKeyService.rotate_key(tenant["tenant_id"])
        return APIKeyRotateResponse(
            new_api_key=new_key,
            message="🔑 Old key revoked. Save your new API key — "
                    "it won't be shown again!"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Key rotation failed: {str(e)}"
        )


@router.put("/webhook")
async def update_webhook(
    webhook_url: str,
    tenant: dict = Depends(verify_api_key)
):
    """Update webhook URL for risk event notifications"""
    await TenantService.update_tenant(
        tenant["tenant_id"],
        {"webhook_url": webhook_url}
    )
    return {"message": f"Webhook URL updated to {webhook_url}"}