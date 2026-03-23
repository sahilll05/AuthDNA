# backend/engines/feature_pipeline.py
import numpy as np
from datetime import datetime
from typing import Dict, Optional, List
from utils.ip_lookup import lookup_ip


# EXACT feature order matching your trained models
FEATURES = [
    "hour_sin", "hour_cos", "hour_deviation", "is_weekend", "is_offhours",
    "new_device", "country_change", "impossible_travel",
    "failed_norm", "resource_sensitivity", "privilege_gap", "login_velocity",
    "multi_attack_flag", "hour_x_newdev", "fail_x_newdev",
]


async def build_features(
    user_id: str,
    ip: str,
    device_fp: str,
    resource: str,
    failed_attempts: int,
    timestamp: str = None,
    user_agent: str = None,
    dna_profile: Optional[Dict] = None,
    login_history: Optional[List[Dict]] = None
) -> Dict:
    """
    Build 15-feature vector matching the trained scaler/models.
    """
    # ── Parse timestamp ──────────────────────────────────────
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.utcnow()
    else:
        dt = datetime.utcnow()

    hour = dt.hour
    day_of_week = dt.weekday()  # 0=Mon, 6=Sun

    # ── 1. hour_sin ──────────────────────────────────────────
    hour_sin = float(np.sin(2 * np.pi * hour / 24))

    # ── 2. hour_cos ──────────────────────────────────────────
    hour_cos = float(np.cos(2 * np.pi * hour / 24))

    # ── 4. is_weekend ────────────────────────────────────────
    is_weekend = 1 if day_of_week >= 5 else 0

    # ── 5. is_offhours ───────────────────────────────────────
    #   Typically: before 6 AM or after 10 PM
    is_offhours = 1 if (hour < 6 or hour >= 22) else 0

    # ── IP geolocation ───────────────────────────────────────
    ip_info = await lookup_ip(ip)
    country = ip_info.get("country", "Unknown")
    city = ip_info.get("city", "Unknown")

    # ── 10. resource_sensitivity ─────────────────────────────
    resource_sensitivity_map = {
        "general": 0.1, "profile": 0.2, "settings": 0.3,
        "documents": 0.4, "admin": 0.7, "financial_data": 0.8,
        "api_keys": 0.9, "admin_panel": 1.0,
    }
    resource_sensitivity = resource_sensitivity_map.get(resource.lower(), 0.3)

    # ── 9. failed_norm ───────────────────────────────────────
    #   Normalize failed_attempts to 0-1 range (cap at 10)
    failed_norm = min(failed_attempts, 10) / 10.0

    # ══════════════════════════════════════════════════════════
    # Behavioral features (depend on DNA profile)
    # ══════════════════════════════════════════════════════════
    new_device = 1
    country_change = 0
    impossible_travel = 0
    hour_deviation = 0.0
    login_velocity = 0.0

    if dna_profile:
        # ── 6. new_device ────────────────────────────────────
        known_devices = dna_profile.get("known_devices", [])
        if device_fp in known_devices:
            new_device = 0

        # ── 7. country_change ────────────────────────────────
        known_countries = dna_profile.get("known_countries", [])
        if known_countries and country not in known_countries:
            country_change = 1

        # ── 8. impossible_travel ─────────────────────────────
        last_login = dna_profile.get("last_login", {})
        if last_login:
            last_country = last_login.get("country", "")
            last_time_str = last_login.get("timestamp", "")
            if last_country and last_country != country and last_time_str:
                try:
                    last_time = datetime.fromisoformat(
                        last_time_str.replace("Z", "+00:00")
                    )
                    time_diff_hours = (dt - last_time).total_seconds() / 3600
                    if time_diff_hours < 3:
                        impossible_travel = 1
                except Exception:
                    pass

        # ── 3. hour_deviation ────────────────────────────────
        avg_hour = dna_profile.get("avg_login_hour", 12.0)
        raw_diff = abs(hour - avg_hour)
        hour_deviation = min(raw_diff, 24 - raw_diff) / 12.0  # 0-1

        # ── 12. login_velocity ───────────────────────────────
        #   Logins per day
        login_count = dna_profile.get("login_count", 0)
        days_active = dna_profile.get("days_active", 1)
        login_velocity = min(login_count / max(days_active, 1), 10.0) / 10.0  # 0-1

    # ── 11. privilege_gap ────────────────────────────────────
    privilege_gap = resource_sensitivity * (
        new_device * 0.3 + country_change * 0.4 + impossible_travel * 0.3
    )

    # ── 13. multi_attack_flag ────────────────────────────────
    #   1 if multiple attack signals fire simultaneously
    attack_signals = sum([
        new_device,
        country_change,
        impossible_travel,
        1 if failed_attempts >= 3 else 0,
        is_offhours,
    ])
    multi_attack_flag = 1 if attack_signals >= 3 else 0

    # ── 14. hour_x_newdev (interaction) ──────────────────────
    hour_x_newdev = hour_deviation * new_device

    # ── 15. fail_x_newdev (interaction) ──────────────────────
    fail_x_newdev = failed_norm * new_device

    # ══════════════════════════════════════════════════════════
    # Build feature dict — MUST match FEATURES order exactly
    # ══════════════════════════════════════════════════════════
    features = {
        "hour_sin":             hour_sin,
        "hour_cos":             hour_cos,
        "hour_deviation":       hour_deviation,
        "is_weekend":           is_weekend,
        "is_offhours":          is_offhours,
        "new_device":           new_device,
        "country_change":       country_change,
        "impossible_travel":    impossible_travel,
        "failed_norm":          failed_norm,
        "resource_sensitivity": resource_sensitivity,
        "privilege_gap":        privilege_gap,
        "login_velocity":       login_velocity,
        "multi_attack_flag":    multi_attack_flag,
        "hour_x_newdev":        hour_x_newdev,
        "fail_x_newdev":        fail_x_newdev,
    }

    # Metadata (not fed to model — used for explainability + logging)
    metadata = {
        "ip": ip,
        "country": country,
        "city": city,
        "isp": ip_info.get("isp", "Unknown"),
        "device_fp": device_fp,
        "resource": resource,
        "hour": hour,
        "timestamp": dt.isoformat(),
        "is_new_user": dna_profile is None,
    }

    return {"features": features, "metadata": metadata}