import math
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any
import numpy as np
import httpx

logger = logging.getLogger(__name__)

RESOURCE_SENSITIVITY = {
    "admin_panel": 1.0, "financial_data": 0.9, "user_management": 0.8,
    "api_keys": 0.85, "billing": 0.7, "settings": 0.5, "reports": 0.4,
    "dashboard": 0.3, "profile": 0.2, "general": 0.1,
}
FEATURE_NAMES = [
    "hour_sin", "hour_cos", "hour_zscore", "is_new_device", "country_change", 
    "impossible_travel", "failed_attempts", "resource_sensitivity", 
    "days_since_last_login", "privilege_gap_score"
]
ROLE_CLEARANCE = {"viewer": 1, "analyst": 2, "developer": 3, "hr": 3, "manager": 4, "admin": 5}
SENS_MAP = {"dashboard": 1, "reports": 2, "profile": 1, "settings": 3, "billing": 3,
            "user_management": 4, "api_keys": 4, "financial_data": 4, "admin_panel": 5, "general": 1}


class FeaturePipeline:
    async def lookup_ip(self, ip: str) -> Dict[str, Any]:
        if ip.startswith(("10.", "172.16.", "192.168.", "127.", "0.")) or ip == "::1":
            return {"country": "Unknown", "city": "Unknown", "isp": "Unknown", "lat": 0.0, "lon": 0.0}
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get(f"http://ip-api.com/json/{ip}")
                d = r.json()
                if d.get("status") == "success":
                    return {"country": d.get("country", "Unknown"), "city": d.get("city", "Unknown"),
                            "isp": d.get("isp", "Unknown"), "lat": d.get("lat", 0.0), "lon": d.get("lon", 0.0),
                            "timezone": d.get("timezone", "UTC")}
        except Exception as e:
            logger.warning(f"IP lookup failed: {e}")
        return {"country": "Unknown", "city": "Unknown", "isp": "Unknown", "lat": 0.0, "lon": 0.0, "timezone": "UTC"}

    async def extract(self, user_id, ip, device_fp, resource, failed_attempts, user_agent, timestamp, dna_profile, role="viewer"):
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                dt = datetime.now(timezone.utc)
        else:
            dt = datetime.now(timezone.utc)

        geo = await self.lookup_ip(ip)

        # Bug Fix: Time varies country to country. Calculate LOCAL hour using IP timezone.
        try:
            import zoneinfo
            tz_str = geo.get("timezone", "UTC")
            dt_local = dt.astimezone(zoneinfo.ZoneInfo(tz_str))
            hour = dt_local.hour
        except Exception:
            hour = dt.hour
        hour_sin = math.sin(2 * math.pi * hour / 24)
        hour_cos = math.cos(2 * math.pi * hour / 24)
        is_weekend = 1.0 if dt.weekday() >= 5 else 0.0
        is_offhours = 1.0 if hour < 6 or hour > 22 else 0.0
        new_device = 0.0
        country_change = 0.0
        impossible_travel = 0.0
        hour_deviation = 0.0
        login_velocity = 0.0

        if dna_profile:
            kd = json.loads(dna_profile.get("known_devices_json", "[]"))
            if device_fp and device_fp not in kd:
                new_device = 1.0
            kc = json.loads(dna_profile.get("known_countries_json", "[]"))
            if geo["country"] != "Unknown" and geo["country"] not in kc:
                country_change = 1.0
            ah = dna_profile.get("avg_login_hour")
            if ah is not None:
                diff = min(abs(hour - ah), 24 - abs(hour - ah))
                hour_deviation = min(diff / 12.0, 1.0)
            lc = dna_profile.get("login_count", 0)
            da = max(dna_profile.get("days_active", 1), 1)
            login_velocity = min((lc / da) / 10.0, 1.0)
        else:
            new_device = 1.0 if device_fp else 0.0

        failed_norm = min(failed_attempts / 10.0, 1.0)
        res_sensitivity = RESOURCE_SENSITIVITY.get(resource, 0.1)
        clearance = ROLE_CLEARANCE.get(role, 1)
        sens_level = SENS_MAP.get(resource, 1)
        privilege_gap = max(0.0, (sens_level - clearance) / 5.0)
        attack_signals = sum([new_device, country_change, impossible_travel,
                              1.0 if failed_attempts >= 3 else 0.0, is_offhours])
        multi_attack_flag = 1.0 if attack_signals >= 3 else 0.0
        
        unusual_resource = False
        if dna_profile:
            cr = json.loads(dna_profile.get("common_resources_json", "[]"))
            if cr and resource not in cr:
                unusual_resource = True

        hour_x_newdev = hour_deviation * new_device
        fail_x_newdev = failed_norm * new_device

        hour_zscore = hour_deviation  # Alias for PRD
        is_new_device = new_device
        # For days_since_last_login, approximate using days_active or last_login
        days_since_last_login = 1.0
        if dna_profile:
            last_ts_str = dna_profile.get("last_login")
            if last_ts_str:
                try:
                    lts = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
                    days_since_last_login = max(0.0, (dt - lts).total_seconds() / 86400.0)
                except:
                    pass
        days_since_last_login = min(days_since_last_login, 90.0)
        privilege_gap_score = privilege_gap

        fd = {
            "hour_sin": round(hour_sin, 6), "hour_cos": round(hour_cos, 6),
            "hour_zscore": round(hour_zscore, 4), "is_new_device": int(is_new_device),
            "country_change": int(country_change), "impossible_travel": int(impossible_travel),
            "failed_attempts": int(min(failed_attempts, 15)), "resource_sensitivity": int(res_sensitivity * 10),
            "days_since_last_login": int(days_since_last_login), "privilege_gap_score": round(privilege_gap_score, 4),
        }
        features = np.array([fd[f] for f in FEATURE_NAMES], dtype=np.float64)
        return {
            "features": features, "feature_dict": fd, "geo": geo, "parsed_hour": hour,
            "flags": {"new_device": bool(new_device), "country_change": bool(country_change),
                      "impossible_travel": bool(impossible_travel), "is_offhours": bool(is_offhours),
                      "is_weekend": bool(is_weekend), "multi_attack_flag": bool(multi_attack_flag),
                      "unusual_resource": unusual_resource},
        }