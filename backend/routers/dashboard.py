# backend/routers/dashboard.py
"""
Dashboard APIs — tenant-scoped analytics and user data.
"""
from fastapi import APIRouter, Depends, Query
from models.schemas import DashboardStats, LoginLogEntry, UserDNAProfile
from middleware.api_key_auth import verify_api_key
from services.tenant_service import TenantService
from services.usage_service import UsageService
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/v1/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    period: str = Query(
        default=None,
        description="Period in YYYY-MM format. Defaults to current month."
    ),
    tenant: dict = Depends(verify_api_key)
):
    """
    Get aggregate statistics for your tenant.
    Shows total logins, blocked count, average risk score, etc.
    """
    tenant_id = tenant["tenant_id"]

    if period is None:
        period = datetime.utcnow().strftime("%Y-%m")

    usage = await UsageService.get_usage(tenant_id, period)

    return DashboardStats(
        total_logins=usage.get("total_calls", 0),
        blocked_logins=usage.get("block_count", 0),
        otp_triggered=usage.get("otp_count", 0),
        allowed_logins=usage.get("allow_count", 0),
        unique_users=0,  # Could be computed from login logs
        avg_risk_score=round(usage.get("avg_score", 0), 1),
        period=period
    )


@router.get("/logs", response_model=List[LoginLogEntry])
async def get_login_logs(
    limit: int = Query(default=50, le=500),
    user_id: Optional[str] = Query(default=None),
    tenant: dict = Depends(verify_api_key)
):
    """
    Get recent login evaluation logs.
    Optionally filter by user_id.
    """
    tenant_id = tenant["tenant_id"]

    logs = await TenantService.get_login_logs(
        tenant_id, limit=limit, user_id=user_id
    )

    return [
        LoginLogEntry(
            user_id=log.get("user_id", ""),
            ip=log.get("ip", ""),
            device_fp=log.get("device_fp", ""),
            resource=log.get("resource", ""),
            score=log.get("score", 0),
            decision=log.get("decision", ""),
            explanation=log.get("explanation", ""),
            timestamp=log.get("timestamp", ""),
            country=log.get("country"),
            city=log.get("city")
        )
        for log in logs
    ]


@router.get("/users/{user_id}/dna", response_model=UserDNAProfile)
async def get_user_dna(
    user_id: str,
    tenant: dict = Depends(verify_api_key)
):
    """
    Get the behavioral DNA profile for a specific user.
    Shows their normal patterns — devices, locations, times.
    """
    tenant_id = tenant["tenant_id"]

    profile = await TenantService.get_dna_profile(tenant_id, user_id)

    if not profile:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f"No DNA profile found for user '{user_id}'. "
                   f"Profile is created after the first login evaluation."
        )

    return UserDNAProfile(
        user_id=user_id,
        avg_login_hour=profile.get("avg_login_hour", 0),
        common_devices=profile.get("known_devices", []),
        common_locations=profile.get("known_countries", []),
        common_resources=profile.get("common_resources", []),
        login_count=profile.get("login_count", 0),
        last_seen=profile.get("last_login", {}).get(
            "timestamp", profile.get("updated_at", "")
        )
    )


@router.get("/users", response_model=List[UserDNAProfile])
async def get_all_users(
    tenant: dict = Depends(verify_api_key)
):
    """
    Get all user DNA profiles for your tenant.
    Useful for the admin dashboard.
    """
    tenant_id = tenant["tenant_id"]
    profiles = await TenantService.get_all_dna_profiles(tenant_id)

    return [
        UserDNAProfile(
            user_id=p.get("user_id", ""),
            avg_login_hour=p.get("avg_login_hour", 0),
            common_devices=p.get("known_devices", []),
            common_locations=p.get("known_countries", []),
            common_resources=p.get("common_resources", []),
            login_count=p.get("login_count", 0),
            last_seen=p.get("last_login", {}).get(
                "timestamp", p.get("updated_at", "")
            )
        )
        for p in profiles
    ]