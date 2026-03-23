# backend/routers/usage.py
"""
Usage tracking router — API call counts, billing info.
"""
from fastapi import APIRouter, Depends, Query
from middleware.api_key_auth import verify_api_key
from services.usage_service import UsageService
from config.settings import settings
from datetime import datetime

router = APIRouter(prefix="/v1/usage", tags=["Usage & Billing"])


@router.get("/current")
async def get_current_usage(
    tenant: dict = Depends(verify_api_key)
):
    """
    Get your current month's API usage and remaining quota.
    """
    tenant_id = tenant["tenant_id"]
    tier = tenant.get("tier", "free")
    period = datetime.utcnow().strftime("%Y-%m")

    usage = await UsageService.get_usage(tenant_id, period)

    from config.settings import TenantTier
    rate_limit = settings.RATE_LIMITS.get(TenantTier(tier), 100)

    # Get current hourly rate
    hourly_count = await UsageService.get_hourly_rate(tenant_id)

    return {
        "tenant_id": tenant_id,
        "tier": tier,
        "period": period,
        "total_calls_this_month": usage.get("total_calls", 0),
        "hourly_rate_limit": rate_limit,
        "hourly_calls_used": hourly_count,
        "hourly_remaining": max(0, rate_limit - hourly_count),
        "breakdown": {
            "allow": usage.get("allow_count", 0),
            "block": usage.get("block_count", 0),
            "otp": usage.get("otp_count", 0),
            "stepup": usage.get("stepup_count", 0)
        },
        "avg_latency_ms": round(usage.get("avg_latency_ms", 0), 1),
        "avg_risk_score": round(usage.get("avg_score", 0), 1)
    }


@router.get("/history")
async def get_usage_history(
    months: int = Query(default=6, le=12),
    tenant: dict = Depends(verify_api_key)
):
    """
    Get historical usage for the last N months.
    """
    tenant_id = tenant["tenant_id"]
    history = []

    now = datetime.utcnow()

    for i in range(months):
        month = now.month - i
        year = now.year
        if month <= 0:
            month += 12
            year -= 1
        period = f"{year}-{month:02d}"

        usage = await UsageService.get_usage(tenant_id, period)
        history.append({
            "period": period,
            "total_calls": usage.get("total_calls", 0),
            "block_count": usage.get("block_count", 0),
            "allow_count": usage.get("allow_count", 0),
            "avg_latency_ms": round(usage.get("avg_latency_ms", 0), 1)
        })

    return {"tenant_id": tenant_id, "history": history}