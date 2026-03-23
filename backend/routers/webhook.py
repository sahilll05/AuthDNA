# backend/routers/webhook.py
"""
Webhook management router.
"""
from fastapi import APIRouter, Depends, HTTPException
from middleware.api_key_auth import verify_api_key
from services.tenant_service import TenantService
from models.schemas import WebhookUpdateRequest

router = APIRouter(prefix="/v1/webhooks", tags=["Webhooks"])


@router.get("/")
async def get_webhook(
    tenant: dict = Depends(verify_api_key)
):
    """Get your current webhook configuration"""
    tenant_data = await TenantService.get_tenant(tenant["tenant_id"])
    return {
        "webhook_url": tenant_data.get("webhook_url"),
        "events": ["risk.block", "risk.stepup", "risk.otp"],
        "status": "active" if tenant_data.get("webhook_url") else "not_configured"
    }


@router.put("/")
async def update_webhook(
    req: WebhookUpdateRequest,
    tenant: dict = Depends(verify_api_key)
):
    """Update webhook URL. We'll POST risk events to this URL."""
    await TenantService.update_tenant(
        tenant["tenant_id"],
        {"webhook_url": req.webhook_url}
    )
    return {
        "message": "Webhook URL updated successfully",
        "webhook_url": req.webhook_url,
        "events": ["risk.block", "risk.stepup", "risk.otp"]
    }


@router.delete("/")
async def delete_webhook(
    tenant: dict = Depends(verify_api_key)
):
    """Remove webhook configuration"""
    await TenantService.update_tenant(
        tenant["tenant_id"],
        {"webhook_url": None}
    )
    return {"message": "Webhook removed successfully"}


@router.post("/test")
async def test_webhook(
    tenant: dict = Depends(verify_api_key)
):
    """
    Send a test webhook to your registered URL.
    """
    tenant_data = await TenantService.get_tenant(tenant["tenant_id"])
    webhook_url = tenant_data.get("webhook_url")

    if not webhook_url:
        raise HTTPException(
            status_code=400,
            detail="No webhook URL configured. Set one first with PUT /v1/webhooks/"
        )

    from services.webhook_service import WebhookService
    from datetime import datetime

    test_payload = {
        "user_id": "test_user@example.com",
        "score": 85.0,
        "decision": "BLOCK",
        "explanation": "This is a test webhook event",
        "ip": "203.0.113.42",
        "country": "Test Country"
    }

    success = await WebhookService.send_webhook(
        webhook_url,
        tenant["tenant_id"],
        "risk.test",
        test_payload
    )

    return {
        "success": success,
        "webhook_url": webhook_url,
        "message": "Test webhook sent!" if success else "Webhook delivery failed"
    }