import math
import numpy as np
from datetime import datetime

# Temporary manual definition of RESOURCES to avoid circular imports 
# or missing variables. This matches user_profiles.py
RESOURCES = {
    "dev_dashboard":    1,   
    "git_server":       2,   
    "reports":          3,   
    "hr_portal":        4,   
    "staging_api":      5,   
    "payroll_system":   6,   
    "user_mgmt":        6,   
    "billing_panel":    9,   
    "iam_console":      10,  
}

def engineer_features(event: dict, user_history: list) -> dict:
    """
    Convert one raw login event into a 10-feature vector.
    """
    hour = event.get("hour", 12)  # default to noon for missing data
    
    # ── FEATURE 1 & 2: Cyclical hour encoding ─────────────────────
    hour_sin = math.sin(2 * math.pi * hour / 24)
    hour_cos = math.cos(2 * math.pi * hour / 24)
    
    # ── FEATURE 3: Z-score of login hour vs user history ───────────
    if len(user_history) >= 5:
        user_hours = [s["hour"] for s in user_history]
        hour_mean  = np.mean(user_hours)
        hour_std   = np.std(user_hours)
    else:
        hour_mean, hour_std = 12.0, 4.0  # neutral defaults for new users
    hour_zscore = (hour - hour_mean) / (hour_std + 0.1)  # +0.1 prevents div/0
    
    # ── FEATURE 4: New device flag ─────────────────────────────────
    current_device = event.get("device_id", "")
    if user_history:
        known_devices = set(s["device_id"] for s in user_history)
        is_new_device = int(current_device not in known_devices)
    else:
        is_new_device = 0  # no history = cannot say it is new
    
    # ── FEATURE 5: Country change flag ─────────────────────────────
    current_country = event.get("country", "")
    if user_history:
        recent_countries = set(s["country"] for s in user_history[-5:])
        country_change = int(current_country not in recent_countries)
    else:
        country_change = 0
    
    # ── FEATURE 6: Impossible travel flag ──────────────────────────
    impossible_travel = 0
    if country_change and user_history:
        last_ts = datetime.fromisoformat(user_history[-1]["timestamp"].replace("Z", "+00:00"))
        current_ts = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        hours_elapsed = (current_ts - last_ts).total_seconds() / 3600
        if hours_elapsed < 6:   # less than 6 hours between countries
            impossible_travel = 1
    
    # ── FEATURE 7: Failed login attempts ───────────────────────────
    failed_attempts = min(event.get("failed_attempts", 0), 15)
    
    # ── FEATURE 8: Resource sensitivity ────────────────────────────
    resource = event.get("resource", "")
    resource_sensitivity = event.get(
        "resource_sensitivity",
        RESOURCES.get(resource, 3)  # default to 3 if unknown resource
    )
    
    # ── FEATURE 9: Days since last login ───────────────────────────
    if user_history:
        last_ts = datetime.fromisoformat(user_history[-1]["timestamp"].replace("Z", "+00:00"))
        current_ts = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        days_since = max(0, (current_ts - last_ts).days)
        days_since = min(days_since, 90)  # cap at 90 days
    else:
        days_since = 30  # neutral default for first-ever login
    
    # ── FEATURE 10: Privilege gap score ────────────────────────────
    role_ceiling = event.get("sensitivity_ceiling", 5)
    gap = resource_sensitivity - role_ceiling
    privilege_gap_score = max(0.0, min(gap / 10.0, 1.0))
    
    # ── RETURN: Fixed-order dict (ORDER IS CRITICAL) ───────────────
    return {
        "hour_sin":            round(float(hour_sin), 6),
        "hour_cos":            round(float(hour_cos), 6),
        "hour_zscore":         round(float(hour_zscore), 6),
        "is_new_device":       int(is_new_device),
        "country_change":      int(country_change),
        "impossible_travel":   int(impossible_travel),
        "failed_attempts":     int(failed_attempts),
        "resource_sensitivity":int(resource_sensitivity),
        "days_since_last_login":int(days_since),
        "privilege_gap_score": round(float(privilege_gap_score), 6),
    }

FEATURE_NAMES = [
    "hour_sin", "hour_cos", "hour_zscore", "is_new_device", "country_change",
    "impossible_travel", "failed_attempts", "resource_sensitivity",
    "days_since_last_login", "privilege_gap_score"
]
