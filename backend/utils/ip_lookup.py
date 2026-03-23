# backend/utils/ip_lookup.py
import httpx
from typing import Dict, Optional
from config.settings import settings
import asyncio

# Simple in-memory cache to avoid hammering ip-api.com
_ip_cache: Dict[str, Dict] = {}


async def lookup_ip(ip: str) -> Dict[str, Optional[str]]:
    """
    Lookup IP geolocation using ip-api.com (free tier: 45 req/min)
    Returns: {country, city, isp, lat, lon, timezone}
    """
    # Check cache first
    if ip in _ip_cache:
        return _ip_cache[ip]

    # Default response for private/invalid IPs
    default = {
        "country": "Unknown",
        "city": "Unknown",
        "isp": "Unknown",
        "lat": 0.0,
        "lon": 0.0,
        "timezone": "UTC"
    }

    # Skip private IPs
    if ip.startswith(("127.", "10.", "192.168.", "172.16.", "0.")):
        _ip_cache[ip] = default
        return default

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.IP_API_URL}{ip}")
            data = response.json()

            if data.get("status") == "success":
                result = {
                    "country": data.get("country", "Unknown"),
                    "city": data.get("city", "Unknown"),
                    "isp": data.get("isp", "Unknown"),
                    "lat": data.get("lat", 0.0),
                    "lon": data.get("lon", 0.0),
                    "timezone": data.get("timezone", "UTC")
                }
                _ip_cache[ip] = result
                return result

    except Exception as e:
        print(f"IP lookup failed for {ip}: {e}")

    _ip_cache[ip] = default
    return default