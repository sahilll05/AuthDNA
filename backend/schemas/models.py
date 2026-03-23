"""
backend/schemas/models.py
══════════════════════════════════════════════════════════════════
All Pydantic request and response schemas for the FastAPI backend.

Every real login sends a LoginRequest.
Every response returns a LoginResponse.
══════════════════════════════════════════════════════════════════
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ══════════════════════════════════════════════════════════════════
# REQUEST — sent by the React frontend on every login
# ══════════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    """
    Sent by the React frontend to POST /evaluate-login.
    All fields come from the real login form + browser fingerprint.
    """
    user_id:            str             # Firebase Auth UID
    resource:           str             # which resource they want to access
    device_fingerprint: str             # hash of User-Agent + screen size etc.
    failed_attempts:    int   = 0       # how many times they failed before this attempt
    session_id:         str   = ""      # current session ID (for graph history)
    daily_login_count:  int   = 1       # how many logins today (from frontend)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id":            "uid_firebase_abc123",
                "resource":           "dashboard",
                "device_fingerprint": "chrome-mac-1920x1080",
                "failed_attempts":    0,
                "session_id":         "sess_xyz789",
                "daily_login_count":  1,
            }
        }


class OTPVerifyRequest(BaseModel):
    """Sent when user submits their OTP code."""
    user_id:    str
    session_id: str
    otp_code:   str


class HeartbeatRequest(BaseModel):
    """Sent every 5 minutes to check if session is still valid."""
    user_id:    str
    session_id: str


# ══════════════════════════════════════════════════════════════════
# RESPONSE — returned to the React frontend
# ══════════════════════════════════════════════════════════════════

class ScoreBreakdown(BaseModel):
    ml_contribution:      float
    dna_contribution:     float
    anomaly_contribution: float
    graph_contribution:   float
    booster_points:       float


class ModelScores(BaseModel):
    xgb_probability: float
    rf_probability:  float
    iso_anomaly:     float
    dna_match:       float
    graph_risk:      float


class SHAPFactor(BaseModel):
    feature:      str
    contribution: float
    label:        str
    direction:    str   # "risk" or "safe"


class ExplanationResponse(BaseModel):
    short_text:   str
    full_text:    str
    key_reasons:  list
    shap_factors: list
    risk_factors: list
    safe_factors: list
    base_score:   float
    used_llm:     bool
    model_used:   str
    tokens_used:  int


class LoginResponse(BaseModel):
    """
    Returned by POST /evaluate-login.
    Contains everything the React dashboard needs to render.
    """
    # Core decision
    decision:        str    # ALLOW | OTP | STEPUP | BLOCK
    final_score:     float  # 0–100
    user_id:         str

    # Score breakdown (for the detail panel)
    score_breakdown: ScoreBreakdown
    model_scores:    ModelScores

    # Signals that fired (for the alerts panel)
    signals_fired:   list

    # Location info (for the dashboard map)
    country:         str = ""
    city:            str = ""
    ip:              str = ""

    # Behavioural DNA (for the radar chart)
    dna_match:       float = 0.5
    drift_type:      str   = "none"
    radar_scores:    dict  = {}

    # Explanation (for the explanation panel)
    explanation:     ExplanationResponse

    # Metadata
    timestamp:       str
    log_id:          str = ""   # Firestore document ID of the login log


class OTPVerifyResponse(BaseModel):
    success:    bool
    message:    str
    new_token:  Optional[str] = None


class DashboardStatsResponse(BaseModel):
    """Returned by GET /dashboard/stats"""
    total_logins:    int
    blocked_logins:  int
    flagged_logins:  int
    allowed_logins:  int
    avg_risk_score:  float
    recent_anomalies: list


class HealthResponse(BaseModel):
    status:   str
    firebase: str
    models:   str
    version:  str = "1.0.0"
