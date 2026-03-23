# backend/config/settings.py
import os
from dotenv import load_dotenv
from enum import Enum

load_dotenv()


class TenantTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Settings:
    # Firebase
    FIREBASE_SERVICE_ACCOUNT_PATH: str = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH", "config/firebase_service_account.json"
    )
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "")

    # Mistral AI
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")

    # API
    API_SECRET_KEY: str = os.getenv("API_SECRET_KEY", "change-me-in-production")
    API_KEY_PREFIX: str = os.getenv("API_KEY_PREFIX", "sk_live_")
    ADMIN_SECRET: str = os.getenv("ADMIN_SECRET", "admin-secret-change-me")

    # Rate limits per tier (requests per hour)
    RATE_LIMITS: dict = {
        TenantTier.FREE: int(os.getenv("RATE_LIMIT_FREE", 100)),
        TenantTier.PRO: int(os.getenv("RATE_LIMIT_PRO", 1000)),
        TenantTier.ENTERPRISE: int(os.getenv("RATE_LIMIT_ENTERPRISE", 10000)),
    }

    # Webhook
    WEBHOOK_TIMEOUT: int = int(os.getenv("WEBHOOK_TIMEOUT", 5))
    WEBHOOK_RETRY_COUNT: int = int(os.getenv("WEBHOOK_RETRY_COUNT", 3))

    # IP Lookup
    IP_API_URL: str = os.getenv("IP_API_URL", "http://ip-api.com/json/")

    # Model paths
    MODEL_DIR: str = "data/models"
    ISO_FOREST_PATH: str = f"{MODEL_DIR}/iso_forest.pkl"
    XGB_MODEL_PATH: str = f"{MODEL_DIR}/xgb_model.pkl"
    RF_MODEL_PATH: str = f"{MODEL_DIR}/rf_model.pkl"
    SCALER_PATH: str = f"{MODEL_DIR}/scaler.pkl"

    # Decision thresholds
    ALLOW_THRESHOLD: float = 30.0
    OTP_THRESHOLD: float = 60.0
    STEPUP_THRESHOLD: float = 80.0
    # Above STEPUP_THRESHOLD = BLOCK


settings = Settings()