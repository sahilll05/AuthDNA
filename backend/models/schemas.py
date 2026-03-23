# backend/models/schemas.py
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================
# Enums
# ============================================================

class Decision(str, Enum):
    ALLOW = "ALLOW"
    OTP = "OTP"
    STEPUP = "STEPUP"
    BLOCK = "BLOCK"


class TenantTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class APIKeyStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


# ============================================================
# Tenant Registration
# ============================================================

class TenantRegisterRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5)
    admin_secret: str = Field(..., description="Admin secret to authorize registration")
    tier: TenantTier = TenantTier.FREE
    webhook_url: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "Acme Corp",
                "email": "admin@acmecorp.com",
                "admin_secret": "admin-secret-change-me",
                "tier": "free",
                "webhook_url": "https://acmecorp.com/webhooks/risk"
            }
        }


class TenantRegisterResponse(BaseModel):
    tenant_id: str
    company_name: str
    api_key: str  # Only shown once at registration
    tier: TenantTier
    rate_limit: int
    message: str


class TenantInfo(BaseModel):
    tenant_id: str
    company_name: str
    email: str
    tier: TenantTier
    created_at: str
    is_active: bool
    webhook_url: Optional[str] = None
    total_api_calls: int = 0


# ============================================================
# API Key Management
# ============================================================

class APIKeyRotateResponse(BaseModel):
    new_api_key: str
    message: str


# ============================================================
# Evaluate Login — the main endpoint
# ============================================================

class EvaluateRequest(BaseModel):
    user_id: str = Field(..., description="Unique user identifier in your system")
    ip: str = Field(..., description="User's real IP address")
    device_fp: str = Field(..., description="Device fingerprint string")
    resource: str = Field(default="general", description="Resource being accessed")
    failed_attempts: int = Field(default=0, ge=0, description="Recent failed login count")
    user_agent: Optional[str] = None
    timestamp: Optional[str] = None  # ISO format, defaults to now

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "bob@acmecorp.com",
                "ip": "203.0.113.42",
                "device_fp": "chrome-win-1920x1080",
                "resource": "financial_data",
                "failed_attempts": 0,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        }


class RiskFactor(BaseModel):
    factor: str
    contribution: float
    description: str


class EvaluateResponse(BaseModel):
    decision: Decision
    score: float = Field(..., ge=0, le=100)
    explanation: str
    risk_factors: List[RiskFactor]
    dna_match: float = Field(..., ge=0, le=100)
    is_new_user: bool
    processing_time_ms: int
    request_id: str
    timestamp: str

    class Config:
        json_schema_extra = {
            "example": {
                "decision": "ALLOW",
                "score": 8.4,
                "explanation": "Normal login from known device at usual time from India",
                "risk_factors": [
                    {"factor": "known_device", "contribution": -5.0, "description": "Device previously seen"},
                    {"factor": "normal_hour", "contribution": -2.0, "description": "Login at usual time"}
                ],
                "dna_match": 92.5,
                "is_new_user": False,
                "processing_time_ms": 187,
                "request_id": "req_abc123",
                "timestamp": "2025-01-15T10:30:00Z"
            }
        }


# ============================================================
# Dashboard Schemas
# ============================================================

class LoginLogEntry(BaseModel):
    user_id: str
    ip: str
    device_fp: str
    resource: str
    score: float
    decision: str
    explanation: str
    timestamp: str
    country: Optional[str] = None
    city: Optional[str] = None


class DashboardStats(BaseModel):
    total_logins: int
    blocked_logins: int
    otp_triggered: int
    allowed_logins: int
    unique_users: int
    avg_risk_score: float
    period: str


class UserDNAProfile(BaseModel):
    user_id: str
    avg_login_hour: float
    common_devices: List[str]
    common_locations: List[str]
    common_resources: List[str]
    login_count: int
    last_seen: str


# ============================================================
# Webhook Schemas
# ============================================================

class WebhookUpdateRequest(BaseModel):
    webhook_url: str


class WebhookPayload(BaseModel):
    event: str  # "risk.block" or "risk.stepup"
    tenant_id: str
    data: Dict[str, Any]
    timestamp: str


# ============================================================
# Usage Schemas
# ============================================================

class UsageRecord(BaseModel):
    tenant_id: str
    period: str  # "2025-01"
    total_calls: int
    allow_count: int
    block_count: int
    otp_count: int
    stepup_count: int
    avg_latency_ms: float
    tier: str
    rate_limit: int