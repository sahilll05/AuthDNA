# backend/services/usage_service.py
from typing import Dict, Optional
from config.firebase import global_collection, tenant_collection
from datetime import datetime


class UsageService:
    """Tracks API usage per tenant for billing and analytics"""

    @staticmethod
    async def log_usage(
        tenant_id: str,
        decision: str,
        latency_ms: int,
        score: float
    ):
        """Log a single API call's usage metrics"""
        now = datetime.utcnow()
        period = now.strftime("%Y-%m")  # Monthly period

        usage_ref = tenant_collection(tenant_id, "usage").document(period)
        usage_doc = usage_ref.get()

        if usage_doc.exists:
            data = usage_doc.to_dict()
            data["total_calls"] = data.get("total_calls", 0) + 1
            data[f"{decision.lower()}_count"] = data.get(f"{decision.lower()}_count", 0) + 1

            # Running average latency
            old_avg = data.get("avg_latency_ms", 0)
            old_count = data.get("total_calls", 1) - 1
            if old_count > 0:
                data["avg_latency_ms"] = (old_avg * old_count + latency_ms) / data["total_calls"]
            else:
                data["avg_latency_ms"] = latency_ms

            # Running average score
            old_score_avg = data.get("avg_score", 0)
            if old_count > 0:
                data["avg_score"] = (old_score_avg * old_count + score) / data["total_calls"]
            else:
                data["avg_score"] = score

            data["last_call"] = now.isoformat()
            usage_ref.set(data)
        else:
            usage_ref.set({
                "tenant_id": tenant_id,
                "period": period,
                "total_calls": 1,
                "allow_count": 1 if decision == "ALLOW" else 0,
                "block_count": 1 if decision == "BLOCK" else 0,
                "otp_count": 1 if decision == "OTP" else 0,
                "stepup_count": 1 if decision == "STEPUP" else 0,
                "avg_latency_ms": latency_ms,
                "avg_score": score,
                "first_call": now.isoformat(),
                "last_call": now.isoformat()
            })

    @staticmethod
    async def get_usage(tenant_id: str, period: str = None) -> Optional[Dict]:
        """Get usage for a specific period (default: current month)"""
        if period is None:
            period = datetime.utcnow().strftime("%Y-%m")

        doc = tenant_collection(tenant_id, "usage").document(period).get()
        if doc.exists:
            return doc.to_dict()
        return {
            "tenant_id": tenant_id,
            "period": period,
            "total_calls": 0,
            "allow_count": 0,
            "block_count": 0,
            "otp_count": 0,
            "stepup_count": 0,
            "avg_latency_ms": 0,
            "avg_score": 0
        }

    @staticmethod
    async def get_hourly_rate(tenant_id: str) -> int:
        """Get number of API calls in the current hour (for rate limiting)"""
        now = datetime.utcnow()
        hour_key = now.strftime("%Y-%m-%d-%H")

        doc = tenant_collection(tenant_id, "rate_tracking").document(hour_key).get()
        if doc.exists:
            return doc.to_dict().get("count", 0)
        return 0

    @staticmethod
    async def increment_hourly_rate(tenant_id: str):
        """Increment hourly rate counter"""
        now = datetime.utcnow()
        hour_key = now.strftime("%Y-%m-%d-%H")

        rate_ref = tenant_collection(tenant_id, "rate_tracking").document(hour_key)
        rate_doc = rate_ref.get()

        if rate_doc.exists:
            rate_ref.update({"count": rate_doc.to_dict().get("count", 0) + 1})
        else:
            rate_ref.set({
                "count": 1,
                "hour": hour_key,
                "tenant_id": tenant_id
            })