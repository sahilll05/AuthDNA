# backend/middleware/rate_limiter.py
from fastapi import Request, HTTPException
from services.usage_service import UsageService
from config.settings import settings


async def check_rate_limit(request: Request):
    """
    Check if tenant has exceeded their hourly rate limit.
    Call this AFTER api_key_auth has set request.state.tenant
    """
    tenant = getattr(request.state, "tenant", None)
    if not tenant:
        return  # No tenant means no rate limit to check

    tenant_id = tenant["tenant_id"]
    tier = tenant.get("tier", "free")

    # Get rate limit for tier
    from config.settings import TenantTier
    rate_limit = settings.RATE_LIMITS.get(TenantTier(tier), 100)

    # Check current hourly usage
    current_count = await UsageService.get_hourly_rate(tenant_id)

    if current_count >= rate_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Rate limit exceeded. Your '{tier}' tier allows "
                           f"{rate_limit} requests/hour. Current: {current_count}.",
                "tier": tier,
                "limit": rate_limit,
                "current": current_count,
                "upgrade_info": "Contact us to upgrade your tier."
            }
        )

    # Increment counter
    await UsageService.increment_hourly_rate(tenant_id)