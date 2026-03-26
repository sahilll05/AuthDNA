import json, random, math
from datetime import datetime, timedelta
from faker import Faker
import sys
sys.path.append('.') # Allow importing from parent if needed
# We are currently in backend/, the script is in backend/scripts/
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from user_profiles import USERS, RESOURCES, device_id

fake = Faker("en_IN")
random.seed(42)          # seed for reproducibility


# ── HELPER: haversine distance (km) between two lat/lon points ─────
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


# ── NORMAL SESSION GENERATOR ───────────────────────────────────────
# This is the baseline. Every user session starts as a normal session.
# Anomaly injectors then modify specific fields to simulate attacks.

def normal_session(user, base_time, day_offset):
    """Generate one realistic normal login for a given user."""
    
    # Login hour: sample from Gaussian around user average
    hour = int(random.gauss(
        (user["hours"][0] + user["hours"][1]) / 2,  # mean
        user["hour_std"]                             # std deviation
    ))
    hour = max(0, min(23, hour))  # clamp to valid range
    
    # Weekday vs weekend logic
    day = day_offset % 7
    is_weekend = day >= 5
    if is_weekend and random.random() > user["weekend_bias"]:
        return None  # this user doesnt work weekends — skip this slot
    
    # Pick a resource from their typical set
    resource = random.choice(user["resources"])
    
    # Timestamp: base_time + day_offset days + random minutes in hour
    ts = base_time + timedelta(
        days=day_offset,
        hours=hour,
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59)
    )
    
    # Failed attempts: mostly 0, occasionally 1 (mistyped password)
    failed = 0
    if random.random() < 0.04:  # 4% of normal logins have 1 failed attempt
        failed = 1
    
    # Device: 90% primary, 10% secondary (e.g., work laptop vs home laptop)
    device_variant = 0
    if user["device_count"] > 1 and random.random() < 0.10:
        device_variant = random.randint(1, user["device_count"] - 1)
    
    return {
        "user_id":             user["id"],
        "role":                user["role"],
        "sensitivity_ceiling": user["sensitivity_ceiling"],
        "timestamp":           ts.isoformat(),
        "hour":                hour,
        "day_of_week":         day,
        "is_weekend":          is_weekend,
        "country":             user["country"],
        "city":                user["city"],
        "lat":                 user["lat"] + random.gauss(0, 0.01),  # small jitter
        "lon":                 user["lon"] + random.gauss(0, 0.01),
        "device_id":           device_id(user["id"], device_variant),
        "primary_device":      device_id(user["id"], 0),
        "resource":            resource,
        "resource_sensitivity": RESOURCES[resource],
        "failed_attempts":     failed,
        "session_duration_s":  int(random.gauss(1800, 600)),  # ~30 min sessions
        "is_anomaly":          False,
        "anomaly_type":        None,
        "risk_label":          0,   # assigned by assign_label() later
    }


# ── SIX ANOMALY INJECTORS ──────────────────────────────────────────
# Each injector takes a normal session and modifies it to simulate
# a specific attack type. The is_anomaly flag tells XGBoost this is
# a high-risk training example.

def inject_impossible_travel(session, user):
    """Simulates: attacker in another country using stolen credentials."""
    s = session.copy()
    # Pick a city far from the user home city
    foreign_cities = {
        "IN": ("GB", "London", 51.5074, -0.1278),
    }
    country, city, lat, lon = foreign_cities.get(user["country"],
        ("US", "New York", 40.7128, -74.0060))
    
    s["country"]      = country
    s["city"]         = city
    s["lat"]          = lat
    s["lon"]          = lon
    s["is_anomaly"]   = True
    s["anomaly_type"] = "impossible_travel"
    return s


def inject_new_device(session, user=None):
    """Simulates: attacker using their own machine with stolen password."""
    s = session.copy()
    # Device variant 9 is always unknown (never generated in normal sessions)
    s["device_id"]    = device_id(s["user_id"], 9)
    s["is_anomaly"]   = True
    s["anomaly_type"] = "new_device"
    return s


def inject_brute_force(session):
    """Simulates: automated password guessing that eventually succeeds."""
    s = session.copy()
    s["failed_attempts"] = random.randint(6, 15)
    s["is_anomaly"]      = True
    s["anomaly_type"]    = "brute_force"
    return s


def inject_unusual_hour(session, user=None):
    """Simulates: after-hours data exfiltration by insider."""
    s = session.copy()
    # Force login to 2-4am regardless of user normal hours
    s["hour"]         = random.randint(2, 4)
    ts = datetime.fromisoformat(s["timestamp"])
    s["timestamp"]    = ts.replace(hour=s["hour"]).isoformat()
    s["is_anomaly"]   = True
    s["anomaly_type"] = "unusual_hour"
    return s


def inject_privilege_escalation(session, user):
    """Simulates: user tries to access resource above their role ceiling."""
    s = session.copy()
    # Find resources above this user's sensitivity ceiling
    escalation_targets = [
        r for r, v in RESOURCES.items()
        if v > user["sensitivity_ceiling"]
    ]
    if not escalation_targets:
        return None  # superadmin has no ceiling — skip
    target = random.choice(escalation_targets)
    s["resource"]             = target
    s["resource_sensitivity"] = RESOURCES[target]
    s["is_anomaly"]           = True
    s["anomaly_type"]         = "privilege_escalation"
    return s


def inject_compound_attack(session, user):
    """Simulates: full account takeover — all signals fire at once.
    This is the highest-risk scenario. Combine multiple anomalies.
    """
    # Stack: impossible travel + new device + high-sensitivity resource
    s = inject_impossible_travel(session, user)
    s = inject_new_device(s, user)
    # Force a high-sensitivity resource target
    high_sensitivity = [r for r, v in RESOURCES.items() if v >= 8]
    if high_sensitivity:
        s["resource"]             = random.choice(high_sensitivity)
        s["resource_sensitivity"] = RESOURCES[s["resource"]]
    s["anomaly_type"] = "compound_attack"
    return s


# ── LABEL ASSIGNMENT ───────────────────────────────────────────────
# This function assigns the training label to each session.
# Labels are integers: 0=low, 1=medium, 2=high.
# XGBoost learns to classify new sessions into these categories.

def assign_label(session):
    """Deterministic label assignment from session features."""
    atype = session.get("anomaly_type")
    
    # Definite high risk
    if atype in ["impossible_travel", "brute_force", "compound_attack"]:
        return 2  # high
    
    # High risk: privilege escalation to very sensitive resource
    if atype == "privilege_escalation":
        if session["resource_sensitivity"] >= 9:
            return 2  # high
        return 1      # medium — escalation to moderately sensitive resource
    
    # Medium risk: single soft anomaly signals
    if atype in ["new_device", "unusual_hour"]:
        return 1  # medium — suspicious but not confirmed
    
    # Low risk: everything looks normal
    return 0


# ── MAIN GENERATION LOOP ───────────────────────────────────────────

def generate_all_sessions(n_days=90, anomaly_rate=0.08):
    """
    Generate n_days of sessions for all users.
    anomaly_rate: fraction of sessions that are anomalous.
    """
    all_sessions = []
    base_time = datetime.now() - timedelta(days=n_days)
    
    anomaly_injectors = [
        inject_impossible_travel,
        inject_new_device,
        inject_brute_force,
        inject_unusual_hour,
        inject_privilege_escalation,
        inject_compound_attack,
    ]
    
    for user in USERS:
        for day_offset in range(n_days):
            # Each user logs in approximately login_freq_per_week / 7 per day
            if random.random() > user["login_freq_per_week"] / 7:
                continue  # no login this day for this user
            
            # Generate a normal session for this user+day
            session = normal_session(user, base_time, day_offset)
            if session is None:
                continue  # weekend skip
            
            # Decide: is this an anomaly?
            if random.random() < anomaly_rate:
                injector = random.choice(anomaly_injectors)
                if injector in [inject_impossible_travel, inject_privilege_escalation, inject_compound_attack]:
                    injected = injector(session, user)
                elif injector in [inject_new_device, inject_unusual_hour]:
                    injected = injector(session)
                else:
                    injected = injector(session)
                if injected is not None:
                    session = injected
            
            # Assign integer label for XGBoost
            session["risk_label"] = assign_label(session)
            all_sessions.append(session)
    
    # Sort chronologically — critical for user history lookups
    all_sessions.sort(key=lambda x: x["timestamp"])
    return all_sessions


if __name__ == "__main__":
    import os
    # Move up one dir if running from scripts/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    sessions = generate_all_sessions(n_days=180, anomaly_rate=0.08)
    
    with open(os.path.join(data_dir, "sessions.json"), "w") as f:
        json.dump(sessions, f, indent=2)
    
    # Print verification summary
    total      = len(sessions)
    anomalies  = sum(1 for s in sessions if s["is_anomaly"])
    by_label   = {0:0, 1:0, 2:0}
    by_type    = {}
    for s in sessions:
        by_label[s["risk_label"]] += 1
        if s["anomaly_type"]:
            by_type[s["anomaly_type"]] = by_type.get(s["anomaly_type"], 0) + 1
    
    print(f"Total sessions:   {total}")
    print(f"Anomalies:        {anomalies} ({anomalies/total*100:.1f}%)")
    print(f"Label 0 (low):    {by_label[0]}")
    print(f"Label 1 (medium): {by_label[1]}")
    print(f"Label 2 (high):   {by_label[2]}")
    print(f"Anomaly types:    {by_type}")
    print("Saved to data/sessions.json")
