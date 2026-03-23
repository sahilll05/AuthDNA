# backend/engines/dna_engine.py
"""
Behavioral DNA Engine — builds and matches user identity fingerprints.
Multi-tenant: DNA profiles are stored per tenant.
"""
from typing import Dict, Optional, List
from datetime import datetime
from services.tenant_service import TenantService


class DNAEngine:
    """
    Builds a behavioral DNA profile for each user (per tenant).
    Compares current login against the profile.
    Returns a DNA match score (0-100).
    """

    @staticmethod
    async def get_or_create_profile(
        tenant_id: str,
        user_id: str
    ) -> Optional[Dict]:
        """Get existing DNA profile or return None for new user"""
        return await TenantService.get_dna_profile(tenant_id, user_id)

    @staticmethod
    def compute_match_score(
        profile: Optional[Dict],
        features: Dict,
        metadata: Dict
    ) -> float:
        """
        Compare current login against DNA profile.
        Returns match score 0-100 (100 = perfect match).
        
        If no profile exists (new user), returns 50 (neutral).
        """
        if profile is None:
            return 50.0  # New user — neutral score

        score = 100.0
        deductions = []

        # 1. Device check (-20 if new device)
        if features.get("new_device", 0) == 1:
            score -= 20
            deductions.append(("new_device", -20))

        # 2. Country check (-25 if country changed)
        if features.get("country_change", 0) == 1:
            score -= 25
            deductions.append(("country_change", -25))

        # 3. Impossible travel (-30)
        if features.get("impossible_travel", 0) == 1:
            score -= 30
            deductions.append(("impossible_travel", -30))

        # 4. Hour deviation (-15 max if far from usual)
        hour_dev = features.get("hour_deviation", 0)
        hour_penalty = hour_dev * 15
        score -= hour_penalty
        if hour_penalty > 2:
            deductions.append(("unusual_hour", -round(hour_penalty, 1)))

        # 5. Failed attempts (-10 per attempt, max -30)
        failed = features.get("failed_attempts", 0)
        fail_penalty = min(failed * 10, 30)
        score -= fail_penalty
        if fail_penalty > 0:
            deductions.append(("failed_attempts", -fail_penalty))

        return max(0, min(100, score))

    @staticmethod
    async def update_profile(
        tenant_id: str,
        user_id: str,
        metadata: Dict,
        features: Dict
    ):
        """
        Update the DNA profile with new login data.
        Called after every successful (non-blocked) login.
        """
        existing = await TenantService.get_dna_profile(tenant_id, user_id)

        if existing is None:
            # Create new profile
            profile = {
                "user_id": user_id,
                "known_devices": [metadata.get("device_fp", "")],
                "known_countries": [metadata.get("country", "Unknown")],
                "known_cities": [metadata.get("city", "Unknown")],
                "avg_login_hour": metadata.get("hour", 12),
                "login_count": 1,
                "days_active": 1,
                "first_seen": datetime.utcnow().isoformat(),
                "last_login": {
                    "country": metadata.get("country", "Unknown"),
                    "city": metadata.get("city", "Unknown"),
                    "device_fp": metadata.get("device_fp", ""),
                    "timestamp": datetime.utcnow().isoformat()
                },
                "common_resources": [metadata.get("resource", "general")]
            }
        else:
            profile = existing.copy()

            # Update known devices (max 10)
            devices = profile.get("known_devices", [])
            device = metadata.get("device_fp", "")
            if device and device not in devices:
                devices.append(device)
                if len(devices) > 10:
                    devices = devices[-10:]
            profile["known_devices"] = devices

            # Update known countries
            countries = profile.get("known_countries", [])
            country = metadata.get("country", "Unknown")
            if country and country not in countries:
                countries.append(country)
            profile["known_countries"] = countries

            # Update known cities
            cities = profile.get("known_cities", [])
            city = metadata.get("city", "Unknown")
            if city and city not in cities:
                cities.append(city)
                if len(cities) > 20:
                    cities = cities[-20:]
            profile["known_cities"] = cities

            # Update average login hour (rolling average)
            old_avg = profile.get("avg_login_hour", 12)
            count = profile.get("login_count", 1)
            new_hour = metadata.get("hour", 12)
            profile["avg_login_hour"] = (old_avg * count + new_hour) / (count + 1)

            # Increment counters
            profile["login_count"] = count + 1

            # Update last login
            profile["last_login"] = {
                "country": metadata.get("country", "Unknown"),
                "city": metadata.get("city", "Unknown"),
                "device_fp": metadata.get("device_fp", ""),
                "timestamp": datetime.utcnow().isoformat()
            }

            # Update resources
            resources = profile.get("common_resources", [])
            resource = metadata.get("resource", "general")
            if resource and resource not in resources:
                resources.append(resource)
            profile["common_resources"] = resources

        await TenantService.store_dna_profile(tenant_id, user_id, profile)