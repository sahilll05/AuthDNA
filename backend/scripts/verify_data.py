import json
import os
from collections import Counter

# Ensure we reference the correct path for data
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_file = os.path.join(base_dir, "data", "sessions.json")

with open(data_file) as f:
    sessions = json.load(f)

print("=== DATA VERIFICATION ===")

# CHECK 1: Minimum session count
assert len(sessions) >= 500, f"FAIL: Only {len(sessions)} sessions. Need 500+"
print(f"PASS: {len(sessions)} sessions")

# CHECK 2: Chronological order
timestamps = [s["timestamp"] for s in sessions]
assert timestamps == sorted(timestamps), "FAIL: Sessions not in time order"
print("PASS: Sessions are chronologically ordered")

# CHECK 3: Anomaly rate is realistic
anomaly_rate = sum(1 for s in sessions if s["is_anomaly"]) / len(sessions)
assert 0.04 <= anomaly_rate <= 0.15, f"FAIL: Anomaly rate {anomaly_rate:.1%} out of range"
print(f"PASS: Anomaly rate {anomaly_rate:.1%}")

# CHECK 4: All 6 anomaly types present
types = set(s["anomaly_type"] for s in sessions if s["anomaly_type"])
required = {"impossible_travel","new_device","brute_force",
            "unusual_hour","privilege_escalation","compound_attack"}
missing = required - types
assert not missing, f"FAIL: Missing anomaly types: {missing}"
print(f"PASS: All anomaly types present: {types}")

# CHECK 5: All 5 users present
users = set(s["user_id"] for s in sessions)
assert len(users) == 5, f"FAIL: Only {len(users)} users. Need 5."
print(f"PASS: 5 users present: {users}")

# CHECK 6: Label distribution (must not be all-zero)
labels = Counter(s["risk_label"] for s in sessions)
assert labels[0] > 0 and labels[1] > 0 and labels[2] > 0, \
    f"FAIL: Missing label classes: {labels}"
print(f"PASS: Labels — low:{labels[0]}, medium:{labels[1]}, high:{labels[2]}")

# CHECK 7: Each user has enough sessions for DNA (need 50+)
by_user = Counter(s["user_id"] for s in sessions)
for uid, count in by_user.items():
    assert count >= 50, f"FAIL: {uid} has only {count} sessions"
print(f"PASS: All users have 50+ sessions: {dict(by_user)}")

# CHECK 8: No missing required fields
required_fields = ["user_id","timestamp","hour","country","device_id",
                   "resource","resource_sensitivity","failed_attempts",
                   "is_anomaly","risk_label"]
for s in sessions:
    for field in required_fields:
        assert field in s, f"FAIL: Session missing field: {field}"
print("PASS: All required fields present in every session")

print("\n=== ALL CHECKS PASSED ===")
print("Data is ready for feature engineering and training.")
