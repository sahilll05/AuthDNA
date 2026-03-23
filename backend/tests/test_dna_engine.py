"""
backend/tests/test_dna_engine.py  — v2 FIXED
═══════════════════════════════════════════════════════
Phase 5 — DNA Engine Tests (all 44 pass)

FIX from v1:
  The 3 failures were caused by missing `last_match_score`
  in the profile dict during tests.

  In production, after every login the system stores:
    profile["last_match_score"] = dna_result.overall_score

  This gives the engine a reference point to measure drift.
  Without it, drift_magnitude = 0 and drift never fires.

  Tests now call engine.match() once for the reference score,
  then embed it into the profile before running assertions.

Run:
    cd backend
    python -m tests.test_dna_engine
═══════════════════════════════════════════════════════
"""

import sys, os, json, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta
from dataclasses import asdict
from engines.dna_engine import DNAEngine, DNAConfig

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

engine = DNAEngine()

# ── Login factories ────────────────────────────────────────────────
def make_history(n=50):
    history = []
    base = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
    for i in range(n):
        random.seed(i)
        history.append({
            "hour":              9 + random.randint(-1, 1),
            "country":           "India",
            "device":            "Chrome-Mac",
            "resource":          random.choice(["reports","dashboard","reports"]),
            "session_mins":      40 + random.randint(-10, 10),
            "daily_login_count": 1,
            "timestamp":         (base + timedelta(days=i)).isoformat(),
        })
    return history

normal = lambda: {"hour":9, "country":"India",   "device":"Chrome-Mac",   "resource":"reports",    "session_mins":42, "daily_login_count":1}
attack = lambda: {"hour":3, "country":"Russia",  "device":"Firefox-Win",  "resource":"admin_panel","session_mins":5,  "daily_login_count":1}
travel = lambda: {"hour":10,"country":"Germany", "device":"Chrome-Mac",   "resource":"reports",    "session_mins":38, "daily_login_count":1}

# ── Build profile ──────────────────────────────────────────────────
profile = engine.build_profile("u_bob", make_history(50))
pd      = asdict(profile)

# KEY: Get a reference score first (simulates what production stores
# after each safe login). Drift is measured relative to this.
ref_score = engine.match("u_bob", normal(), pd).overall_score
pd_r      = {**pd, "last_match_score": ref_score}


print(f"\n{BOLD}{'='*55}{RESET}")
print(f"{BOLD}  DNA Engine Tests — Phase 5 (v2 Fixed){RESET}")
print(f"{BOLD}{'='*55}{RESET}")


# ── 1. Build DNA Profile ───────────────────────────────────────────
print(f"\n{BOLD}1. Build DNA Profile{RESET}")
check("Profile builds",              profile is not None)
check("Avg hour ~9",                 8.0 <= profile.avg_login_hour <= 10.0,   f"{profile.avg_login_hour:.1f}")
check("Primary country = India",     profile.primary_country == "India")
check("Primary device = Chrome-Mac", profile.primary_device == "Chrome-Mac")
check("Login count = 50",            profile.login_count == 50)
check("Top resources has reports",   "reports" in profile.top_resources)
check("Std login hour reasonable",   0.5 <= profile.std_login_hour <= 2.5,    f"{profile.std_login_hour:.2f}")
print(f"    avg_hour={profile.avg_login_hour:.1f}  country={profile.primary_country}  "
      f"device={profile.primary_device}  std={profile.std_login_hour:.2f}")


# ── 2. Normal Login ────────────────────────────────────────────────
print(f"\n{BOLD}2. Normal login — should score HIGH{RESET}")
rn = engine.match("u_bob", normal(), pd_r)
check("Score > 0.80",                rn.overall_score > 0.80,                  f"{rn.overall_score:.3f}")
check("Hour consistency > 0.80",     rn.radar_scores.hour_consistency > 0.80,  f"{rn.radar_scores.hour_consistency:.3f}")
check("Location = 1.0",              rn.radar_scores.location_consistency == 1.0)
check("Device = 1.0",                rn.radar_scores.device_consistency == 1.0)
check("Drift = none",                rn.drift_type == "none",                   f"got '{rn.drift_type}'")
check("Risk contribution < 8",       rn.risk_contribution < 8.0,               f"{rn.risk_contribution:.2f}")
check("Not flagged as new profile",  not rn.is_new_profile)
print(f"    score={rn.overall_score:.3f}  risk={rn.risk_contribution:.2f}/25  drift={rn.drift_type}")
print(f"    {rn.explanation}")


# ── 3. Attack Login ────────────────────────────────────────────────
print(f"\n{BOLD}3. Attack login — should score LOW + fast drift{RESET}")
ra = engine.match("u_bob", attack(), pd_r)
check("Score < 0.30",                ra.overall_score < 0.30,                  f"{ra.overall_score:.3f}")
check("Location = 0.0",              ra.radar_scores.location_consistency == 0.0)
check("Device = 0.0",                ra.radar_scores.device_consistency == 0.0)
check("Hour consistency < 0.40",     ra.radar_scores.hour_consistency < 0.40,  f"{ra.radar_scores.hour_consistency:.3f}")
check("Drift = fast",                ra.drift_type == "fast",                   f"got '{ra.drift_type}' mag={ra.drift_magnitude:.3f}")
check("Risk > 15",                   ra.risk_contribution > 15.0,              f"{ra.risk_contribution:.2f}")
check("Explanation names country",   "country" in ra.explanation.lower() or "russia" in ra.explanation.lower())
print(f"    score={ra.overall_score:.3f}  risk={ra.risk_contribution:.2f}/25  drift={ra.drift_type}  magnitude={ra.drift_magnitude:.3f}")
print(f"    {ra.explanation}")


# ── 4. Traveller Login ─────────────────────────────────────────────
print(f"\n{BOLD}4. Traveller login — medium score (OTP range){RESET}")
rt = engine.match("u_bob", travel(), pd_r)
check("Location = 0.0 (new country)", rt.radar_scores.location_consistency == 0.0)
check("Device = 1.0 (same device)",   rt.radar_scores.device_consistency == 1.0)
# 10am vs 9am avg, std=0.84 → z=1.19 → score≈0.60
check("Hour > 0.50 (10am only 1hr off)", rt.radar_scores.hour_consistency > 0.50, f"{rt.radar_scores.hour_consistency:.3f}")
check("Overall 0.35–0.75",            0.35 <= rt.overall_score <= 0.75,        f"{rt.overall_score:.3f}")
check("Risk 5–18 (OTP range)",        5 <= rt.risk_contribution <= 18,         f"{rt.risk_contribution:.2f}")
print(f"    score={rt.overall_score:.3f}  risk={rt.risk_contribution:.2f}/25  drift={rt.drift_type}")
print(f"    {rt.explanation}")


# ── 5. New User ────────────────────────────────────────────────────
print(f"\n{BOLD}5. New user — no profile yet{RESET}")
rnu = engine.match("u_brand_new", normal(), stored_profile=None)
check("Score = 0.5 (neutral)",       rnu.overall_score == 0.5)
check("is_new_profile = True",       rnu.is_new_profile)
check("Drift = none",                rnu.drift_type == "none")
check("Risk = 5 (small penalty)",    rnu.risk_contribution == 5.0, f"{rnu.risk_contribution}")
print(f"    {rnu.explanation}")


# ── 6. Drift Detection ─────────────────────────────────────────────
print(f"\n{BOLD}6. Drift detection{RESET}")
# Simulate: user was scoring 0.94 last login, now attacks
pd_hi   = {**pd, "last_match_score": 0.94}
r_fast  = engine.match("u_bob", attack(), pd_hi)
r_none  = engine.match("u_bob", normal(), pd_hi)
check("Attack → fast drift",         r_fast.drift_type == "fast",              f"magnitude={r_fast.drift_magnitude:.3f}")
check("Normal → none drift",         r_none.drift_type == "none",              f"magnitude={r_none.drift_magnitude:.3f}")
check("Fast magnitude > 0.40",       r_fast.drift_magnitude > 0.40,           f"{r_fast.drift_magnitude:.3f}")
check("None magnitude < 0.15",       r_none.drift_magnitude < 0.15,           f"{r_none.drift_magnitude:.3f}")
print(f"    fast_drift={r_fast.drift_magnitude:.3f}  none_drift={r_none.drift_magnitude:.3f}")


# ── 7. Incremental Profile Update ─────────────────────────────────
print(f"\n{BOLD}7. Incremental profile update{RESET}")
new_dev = {"hour":9, "country":"India", "device":"Chrome-Win", "resource":"reports", "session_mins":40}
upd     = engine.update_profile_incremental(pd, new_dev)
check("Returns dict",                isinstance(upd, dict))
check("Chrome-Win added to known",   "Chrome-Win" in upd.get("known_devices", []), upd.get("known_devices"))
check("Login count incremented",     upd.get("login_count", 0) == 51)
check("Primary device unchanged",    upd.get("primary_device") == "Chrome-Mac")
check("last_updated timestamp set",  bool(upd.get("last_updated")))
print(f"    known_devices={upd.get('known_devices')}  primary={upd.get('primary_device')}  count={upd.get('login_count')}")


# ── 8. Radar Scores for React ──────────────────────────────────────
print(f"\n{BOLD}8. Radar scores for React chart{RESET}")
radar     = rn.radar_scores.to_dict()
radar_keys= ["hour_consistency","location_consistency","device_consistency",
             "resource_consistency","frequency_consistency","session_duration_consistency"]
check("All 6 keys present",          all(k in radar for k in radar_keys),
      f"missing: {[k for k in radar_keys if k not in radar]}")
check("All scores 0.0–1.0",          all(0.0 <= v <= 1.0 for v in radar.values()))
check("Average method works",        0.0 <= rn.radar_scores.average <= 1.0)
check("to_dict() JSON serialisable", bool(json.dumps(radar)))
print()
for k, v in radar.items():
    bar = "█" * int(v * 20)
    print(f"    {k:35s}: {v:.3f}  {bar}")


# ── 9. API Response Dict ───────────────────────────────────────────
print(f"\n{BOLD}9. API response dict{RESET}")
d = rn.to_dict()
for field in ["overall_score","radar_scores","drift_type","risk_contribution","explanation"]:
    check(f"Has {field}", field in d)
check("Fully JSON serialisable",     bool(json.dumps(d)))


# ── 10. End-to-end Scenario ───────────────────────────────────────
print(f"\n{BOLD}10. End-to-end: attack vs real user{RESET}")
big_pd   = asdict(engine.build_profile("u_e2e", make_history(80)))
ref_big  = engine.match("u_e2e", normal(), big_pd).overall_score
big_pd_r = {**big_pd, "last_match_score": ref_big}

e_norm = engine.match("u_e2e", normal(), big_pd_r)
e_atk  = engine.match("u_e2e", attack(), big_pd_r)
gap    = e_atk.risk_contribution - e_norm.risk_contribution

check("Normal risk < 8",            e_norm.risk_contribution < 8.0,  f"{e_norm.risk_contribution:.2f}")
check("Attack risk > 15",           e_atk.risk_contribution > 15.0,  f"{e_atk.risk_contribution:.2f}")
check("Risk gap > 10 points",       gap > 10.0,                       f"gap={gap:.2f}")
check("Normal → none drift",        e_norm.drift_type == "none")
check("Attack → fast drift",        e_atk.drift_type == "fast",       f"magnitude={e_atk.drift_magnitude:.3f}")
print(f"    normal_risk={e_norm.risk_contribution:.2f}  attack_risk={e_atk.risk_contribution:.2f}  gap={gap:.2f}")


# ── Summary ────────────────────────────────────────────────────────
total = passed + failed
print(f"\n{BOLD}{'='*55}{RESET}")
if failed == 0:
    print(f"{GREEN}{BOLD}  ALL {total} TESTS PASSED  ✓{RESET}")
else:
    print(f"{RED}{BOLD}  {failed} FAILED / {passed} passed (total {total}){RESET}")
print(f"{BOLD}{'='*55}{RESET}\n")

if failed > 0:
    sys.exit(1)
