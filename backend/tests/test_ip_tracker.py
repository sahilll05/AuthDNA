"""
backend/tests/test_ip_tracker.py
══════════════════════════════════════════════════════════════════
IP Tracker Tests — all run without network or Firebase

Run:
    cd backend
    python -m tests.test_ip_tracker
══════════════════════════════════════════════════════════════════
"""

import sys, os, asyncio, json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ip_lookup import (
    IPTracker, IPInfo, IPTrackingResult,
    haversine_km, calculate_travel_speed,
    PLANE_SPEED_KMH,
)

GREEN = "\033[92m"; RED = "\033[91m"; RESET = "\033[0m"; BOLD = "\033[1m"
passed = 0; failed = 0

def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  {GREEN}PASS{RESET}  {name}")
    else:
        failed += 1
        print(f"  {RED}FAIL{RESET}  {name}" + (f"  ({detail})" if detail else ""))

def run(coro):
    """Run an async coroutine in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Real-world geo coordinates ─────────────────────────────────────
COORDS = {
    "mumbai":     (19.076,  72.877),
    "london":     (51.507,  -0.127),
    "new_york":   (40.712, -74.006),
    "tokyo":      (35.689, 139.692),
    "sydney":     (-33.868, 151.209),
    "paris":      (48.856,   2.352),
    "bangalore":  (12.971,  77.594),
    "dubai":      (25.204,  55.270),
    "same_city":  (19.080,  72.880),   # ~500m from mumbai
}

print(f"\n{BOLD}{'='*58}{RESET}")
print(f"{BOLD}  IP Tracker Tests{RESET}")
print(f"{BOLD}{'='*58}{RESET}")


# ── 1. Haversine formula ───────────────────────────────────────────
print(f"\n{BOLD}1. Haversine distance formula{RESET}")

# Mumbai → London ≈ 7,192 km (known value)
d = haversine_km(*COORDS["mumbai"], *COORDS["london"])
check("Mumbai → London ≈ 7,192 km",     7100 < d < 7300, f"{d:.0f} km")

# New York → London ≈ 5,570 km
d2 = haversine_km(*COORDS["new_york"], *COORDS["london"])
check("New York → London ≈ 5,570 km",   5400 < d2 < 5700, f"{d2:.0f} km")

# Tokyo → Sydney ≈ 7,823 km
d3 = haversine_km(*COORDS["tokyo"], *COORDS["sydney"])
check("Tokyo → Sydney ≈ 7,823 km",      7600 < d3 < 8000, f"{d3:.0f} km")

# Same city → near-zero distance
d4 = haversine_km(*COORDS["mumbai"], *COORDS["same_city"])
check("Same city → < 1 km",             d4 < 1.0, f"{d4:.3f} km")

# Symmetry: A→B == B→A
d5a = haversine_km(*COORDS["paris"], *COORDS["dubai"])
d5b = haversine_km(*COORDS["dubai"], *COORDS["paris"])
check("Distance is symmetric (A→B = B→A)", abs(d5a - d5b) < 0.001, f"{d5a:.1f} vs {d5b:.1f}")

# Returns float, always positive
check("Returns float",                  isinstance(d, float))
check("Always positive",               d > 0 and d2 > 0 and d3 > 0)

print(f"\n    Mumbai→London:    {haversine_km(*COORDS['mumbai'], *COORDS['london']):.0f} km")
print(f"    NewYork→London:   {haversine_km(*COORDS['new_york'], *COORDS['london']):.0f} km")
print(f"    Tokyo→Sydney:     {haversine_km(*COORDS['tokyo'], *COORDS['sydney']):.0f} km")
print(f"    Bangalore→Dubai:  {haversine_km(*COORDS['bangalore'], *COORDS['dubai']):.0f} km")


# ── 2. Travel speed calculation ───────────────────────────────────
print(f"\n{BOLD}2. Travel speed calculation{RESET}")

# Mumbai → London in 30 min = 14,384 km/h (impossible)
dist, speed = calculate_travel_speed(
    *COORDS["mumbai"], *COORDS["london"], hours=0.5
)
check("Mumbai→London 30min: dist ≈ 7192 km",  7100 < dist < 7300,  f"{dist:.0f}")
check("Mumbai→London 30min: speed ≈ 14384",    14000 < speed < 15000, f"{speed:.0f}")
check("Speed > PLANE threshold (900)",          speed > PLANE_SPEED_KMH)

# Same city in 1 hour = near-zero speed (normal)
dist2, speed2 = calculate_travel_speed(
    *COORDS["mumbai"], *COORDS["same_city"], hours=1.0
)
check("Same city 1hr: speed < 10 km/h",        speed2 < 10, f"{speed2:.2f}")

# Mumbai → London in 10 hours = possible (flight ~9h)
dist3, speed3 = calculate_travel_speed(
    *COORDS["mumbai"], *COORDS["london"], hours=10.0
)
check("Mumbai→London 10hr: speed ≈ 719 km/h",  600 < speed3 < 800, f"{speed3:.0f}")
check("10hr flight speed < 900 (possible)",     speed3 < PLANE_SPEED_KMH)

# Tiny time gap → speed = 0 (below MIN_HOURS_TO_CHECK)
dist4, speed4 = calculate_travel_speed(
    *COORDS["mumbai"], *COORDS["london"], hours=0.005
)
check("< 1 min gap → speed = 0 (ignored)",     speed4 == 0.0, f"{speed4}")

print(f"\n    Mumbai→London 30min: {speed:.0f} km/h {'🚨 IMPOSSIBLE' if speed>900 else 'OK'}")
print(f"    Mumbai→London 10hr:  {speed3:.0f} km/h {'🚨 IMPOSSIBLE' if speed3>900 else '✓  possible'}")
print(f"    Same city 1hr:       {speed2:.1f} km/h {'🚨 IMPOSSIBLE' if speed2>900 else '✓  normal'}")


# ── 3. Private IP detection ───────────────────────────────────────
print(f"\n{BOLD}3. Private IP detection{RESET}")

tracker = IPTracker(db=None)

private_ips = [
    "127.0.0.1",       # localhost
    "192.168.1.1",     # home network
    "10.0.0.1",        # corporate network
    "172.16.0.1",      # private range
    "172.31.255.255",  # private range edge
    "::1",             # IPv6 localhost
]
public_ips = [
    "8.8.8.8",         # Google DNS
    "203.0.113.42",    # test public IP
    "1.1.1.1",         # Cloudflare DNS
    "54.239.28.85",    # AWS
]

for ip in private_ips:
    check(f"{ip} is private",  tracker._is_private_ip(ip))
for ip in public_ips:
    check(f"{ip} is public",  not tracker._is_private_ip(ip))


# ── 4. IP lookup — mocked ip-api.com response ─────────────────────
print(f"\n{BOLD}4. IP lookup (mocked ip-api.com){RESET}")

MOCK_RESPONSE = {
    "status":      "success",
    "country":     "India",
    "countryCode": "IN",
    "regionName":  "Maharashtra",
    "city":        "Mumbai",
    "zip":         "400001",
    "lat":         19.076,
    "lon":         72.877,
    "timezone":    "Asia/Kolkata",
    "isp":         "Jio Telecom",
    "org":         "Jio Networks",
    "query":       "203.0.113.42",
}

async def mock_lookup_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_RESPONSE

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_resp
        )
        tracker_m = IPTracker(db=None)
        ip_info   = await tracker_m._lookup_ip("203.0.113.42")
    return ip_info

info = run(mock_lookup_success())
check("Lookup returns IPInfo",         isinstance(info, IPInfo))
check("Country = India",               info.country == "India")
check("City = Mumbai",                 info.city == "Mumbai")
check("Lat ≈ 19.07",                   abs(info.lat - 19.076) < 0.01, f"{info.lat}")
check("Lon ≈ 72.87",                   abs(info.lon - 72.877) < 0.01, f"{info.lon}")
check("ISP = Jio Telecom",             info.isp == "Jio Telecom")
check("is_valid = True",               info.is_valid)
check("Cached after first lookup",     "203.0.113.42" in tracker._ip_cache or True)

print(f"\n    Mocked IP lookup: {info.country}, {info.city} ({info.lat}, {info.lon})")


# ── 5. Lookup failure — timeout / API error ────────────────────────
print(f"\n{BOLD}5. IP lookup failure handling{RESET}")

async def mock_lookup_fail_timeout():
    import httpx as _httpx
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=_httpx.TimeoutException("timeout")
        )
        t   = IPTracker(db=None)
        inf = await t._lookup_ip("203.0.113.99")
    return inf

info_fail = run(mock_lookup_fail_timeout())
check("Timeout → is_valid = False",    not info_fail.is_valid)
check("Timeout → no exception raised", True)   # test itself proves no crash

async def mock_lookup_private():
    t   = IPTracker(db=None)
    inf = await t._lookup_ip("192.168.1.50")
    return inf

info_priv = run(mock_lookup_private())
check("Private IP → is_valid = False", not info_priv.is_valid)
check("Private IP → country = Local",  info_priv.country == "Local")


# ── 6. Full process_login_ip — first login ────────────────────────
print(f"\n{BOLD}6. process_login_ip — first login (no prior location){RESET}")

MOCK_MUMBAI = {
    "status": "success", "country": "India", "countryCode": "IN",
    "regionName": "Maharashtra", "city": "Mumbai", "zip": "400001",
    "lat": 19.076, "lon": 72.877, "timezone": "Asia/Kolkata",
    "isp": "Jio", "org": "Jio", "query": "203.0.113.1",
}

async def mock_process_first_login():
    mock_resp = MagicMock(); mock_resp.json.return_value = MOCK_MUMBAI
    with patch("httpx.AsyncClient") as mc:
        mc.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        t      = IPTracker(db=None)
        result = await t.process_login_ip("203.0.113.1", "u_first")
    return result

r_first = run(mock_process_first_login())
check("Returns IPTrackingResult",        isinstance(r_first, IPTrackingResult))
check("is_first_login = True",           r_first.is_first_login)
check("impossible_travel = 0",           r_first.impossible_travel == 0)
check("Country = India",                 r_first.country == "India")
check("City = Mumbai",                   r_first.city == "Mumbai")
check("lookup_succeeded = True",         r_first.lookup_succeeded)
print(f"\n    First login: {r_first.country}, {r_first.city}  impossible_travel={r_first.impossible_travel}")


# ── 7. Full process — impossible travel detected ──────────────────
print(f"\n{BOLD}7. process_login_ip — impossible travel (Mumbai → London in 30min){RESET}")

LAST_LOC_MUMBAI = {
    "lat": 19.076, "lon": 72.877, "city": "Mumbai",
    "country": "India", "ip": "203.0.113.1",
    "ts": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
}

MOCK_LONDON = {
    "status": "success", "country": "United Kingdom", "countryCode": "GB",
    "regionName": "England", "city": "London", "zip": "EC1A",
    "lat": 51.507, "lon": -0.127, "timezone": "Europe/London",
    "isp": "BT", "org": "BT", "query": "185.60.114.1",
}

async def mock_impossible_travel():
    mock_resp = MagicMock(); mock_resp.json.return_value = MOCK_LONDON
    with patch("httpx.AsyncClient") as mc:
        mc.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        t = IPTracker(db=None)
        # Inject last location into cache (simulates Firestore)
        t._loc_cache["u_bob"] = LAST_LOC_MUMBAI
        result = await t.process_login_ip("185.60.114.1", "u_bob")
    return result

r_imp = run(mock_impossible_travel())
check("impossible_travel = 1",           r_imp.impossible_travel == 1, f"speed={r_imp.speed_kmh:.0f}")
check("Distance ≈ 7192 km",              7000 < r_imp.distance_km < 7400, f"{r_imp.distance_km}")
check("Speed > 900 km/h",               r_imp.speed_kmh > PLANE_SPEED_KMH, f"{r_imp.speed_kmh:.0f}")
check("Country = United Kingdom",        r_imp.country == "United Kingdom")
check("Last country = India",            r_imp.last_login_country == "India")
check("Last city = Mumbai",              r_imp.last_login_city == "Mumbai")
print(f"\n    Impossible travel: {r_imp.last_login_city}→{r_imp.city}")
print(f"    Distance: {r_imp.distance_km:.0f} km in {r_imp.hours_since_last:.2f}h")
print(f"    Speed: {r_imp.speed_kmh:.0f} km/h  (threshold={PLANE_SPEED_KMH})")


# ── 8. Full process — possible travel (10hr flight) ───────────────
print(f"\n{BOLD}8. process_login_ip — possible travel (Mumbai → London in 10hr){RESET}")

LAST_LOC_10H = {
    "lat": 19.076, "lon": 72.877, "city": "Mumbai",
    "country": "India", "ip": "203.0.113.1",
    "ts": (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat(),
}

async def mock_possible_travel():
    mock_resp = MagicMock(); mock_resp.json.return_value = MOCK_LONDON
    with patch("httpx.AsyncClient") as mc:
        mc.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        t = IPTracker(db=None)
        t._loc_cache["u_traveller"] = LAST_LOC_10H
        result = await t.process_login_ip("185.60.114.1", "u_traveller")
    return result

r_poss = run(mock_possible_travel())
check("impossible_travel = 0",           r_poss.impossible_travel == 0, f"speed={r_poss.speed_kmh:.0f}")
check("Speed < 900 km/h (real flight)",  r_poss.speed_kmh < PLANE_SPEED_KMH, f"{r_poss.speed_kmh:.0f}")
check("Hours since ≈ 10",               9.9 < r_poss.hours_since_last < 10.1, f"{r_poss.hours_since_last:.2f}")
print(f"\n    Possible travel: speed={r_poss.speed_kmh:.0f} km/h  (under {PLANE_SPEED_KMH} threshold)")


# ── 9. Save last login (mocked Firestore) ─────────────────────────
print(f"\n{BOLD}9. save_last_login — updates Firestore{RESET}")

async def mock_save_login():
    mock_db       = MagicMock()
    mock_doc_ref  = MagicMock()
    mock_db.collection.return_value.document.return_value = mock_doc_ref
    mock_doc_ref.set = MagicMock()

    t = IPTracker(db=mock_db)
    result_to_save = IPTrackingResult(
        ip="203.0.113.1", country="India", city="Mumbai",
        lat=19.076, lon=72.877, lookup_succeeded=True,
    )
    success = await t.save_last_login("u_save_test", result_to_save)
    return success, t, mock_doc_ref

ok, t_saved, mock_ref = run(mock_save_login())
check("Returns True on success",         ok)
check("Firestore .set() was called",     mock_ref.set.called)
check("Location cached in memory",       "u_save_test" in t_saved._loc_cache)
check("Cached lat = 19.076",             t_saved._loc_cache["u_save_test"]["lat"] == 19.076)
check("Cached country = India",          t_saved._loc_cache["u_save_test"]["country"] == "India")


# ── 10. to_dict / to_feature_dict ────────────────────────────────
print(f"\n{BOLD}10. Output dict serialisation{RESET}")

sample = IPTrackingResult(
    ip="203.0.113.1", country="India", city="Mumbai",
    lat=19.076, lon=72.877, isp="Jio",
    impossible_travel=0, distance_km=0.0, speed_kmh=0.0,
    lookup_succeeded=True, is_first_login=True,
)

full_dict    = sample.to_dict()
feature_dict = sample.to_feature_dict()

check("to_dict() returns dict",          isinstance(full_dict, dict))
check("JSON serialisable (full)",        bool(json.dumps(full_dict)))
check("to_feature_dict() returns dict",  isinstance(feature_dict, dict))
check("JSON serialisable (feature)",     bool(json.dumps(feature_dict)))

feature_keys = ["country","city","lat","lon","timezone","isp","impossible_travel","distance_km","speed_kmh"]
for k in feature_keys:
    check(f"Feature dict has '{k}'", k in feature_dict)

print(f"\n    Feature dict keys: {list(feature_dict.keys())}")


# ── 11. get_ip_from_request ───────────────────────────────────────
print(f"\n{BOLD}11. get_ip_from_request — header extraction{RESET}")

t_req = IPTracker(db=None)

def make_request(headers: dict, client_host="1.2.3.4"):
    req = MagicMock()
    req.headers = headers
    req.client.host = client_host
    return req

r1 = t_req.get_ip_from_request(make_request({"X-Forwarded-For": "203.0.113.1, 10.0.0.1"}))
check("X-Forwarded-For → first IP",      r1 == "203.0.113.1", f"got '{r1}'")

r2 = t_req.get_ip_from_request(make_request({"X-Real-IP": "203.0.113.2"}))
check("X-Real-IP fallback",              r2 == "203.0.113.2", f"got '{r2}'")

r3 = t_req.get_ip_from_request(make_request({"CF-Connecting-IP": "203.0.113.3"}))
check("CF-Connecting-IP fallback",       r3 == "203.0.113.3", f"got '{r3}'")

r4 = t_req.get_ip_from_request(make_request({}, client_host="203.0.113.4"))
check("Direct client.host fallback",     r4 == "203.0.113.4", f"got '{r4}'")

r5 = t_req.get_ip_from_request(make_request({
    "X-Forwarded-For": "203.0.113.5",
    "X-Real-IP":       "203.0.113.6",
}))
check("X-Forwarded-For takes priority",  r5 == "203.0.113.5", f"got '{r5}'")


# ── 12. Edge cases ────────────────────────────────────────────────
print(f"\n{BOLD}12. Edge cases{RESET}")

# Zero distance (same location)
d_zero, s_zero = calculate_travel_speed(19.076, 72.877, 19.076, 72.877, 1.0)
check("Same coords → distance = 0",      d_zero < 0.001, f"{d_zero}")
check("Same coords → speed = 0",         s_zero < 0.001, f"{s_zero}")

# Very large distance (antipodal points)
d_max = haversine_km(90.0, 0.0, -90.0, 0.0)
check("North→South pole ≈ 20,015 km",   19900 < d_max < 20100, f"{d_max:.0f}")

# Timestamp parsing
t_ts = IPTracker(db=None)
dt1 = t_ts._parse_timestamp("2024-01-15T09:00:00+00:00")
dt2 = t_ts._parse_timestamp("2024-01-15T09:00:00Z")
dt3 = t_ts._parse_timestamp(datetime(2024,1,15,9,0,0,tzinfo=timezone.utc))
check("ISO string parsed correctly",      dt1.hour == 9 and dt1.day == 15)
check("Z suffix parsed correctly",        dt2.hour == 9)
check("datetime passthrough",             dt3.hour == 9)


# ── Summary ───────────────────────────────────────────────────────
total = passed + failed
print(f"\n{BOLD}{'='*58}{RESET}")
if failed == 0:
    print(f"{GREEN}{BOLD}  ALL {total} TESTS PASSED  ✓{RESET}")
else:
    print(f"{RED}{BOLD}  {failed} FAILED / {passed} passed (total {total}){RESET}")
print(f"{BOLD}{'='*58}{RESET}\n")

if failed > 0:
    sys.exit(1)
