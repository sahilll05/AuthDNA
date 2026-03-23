"""
backend/tests/test_risk_engine.py
══════════════════════════════════════════════════════════════════
Phase 7 — Risk Engine Tests

Tests use REAL-WORLD scenarios including:
  - Normal login from home country
  - VPN login (different country, but otherwise normal)
  - Attacker with correct password
  - Impossible travel via VPN to distant location
  - Privilege escalation attempt
  - Brute force with correct device

Run:
    cd backend
    python -m tests.test_risk_engine
══════════════════════════════════════════════════════════════════
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.risk_engine import (
    RiskEngine, MLScores, DNAScores, GraphScores,
    IPSignals, RiskResult,
    THRESHOLD_ALLOW, THRESHOLD_OTP, THRESHOLD_STEPUP,
)

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW="\033[93m"
RESET = "\033[0m";  BOLD = "\033[1m"
passed = 0; failed = 0

def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  {GREEN}PASS{RESET}  {name}")
    else:
        failed += 1
        print(f"  {RED}FAIL{RESET}  {name}" + (f"  ({detail})" if detail else ""))

engine = RiskEngine()

# ── Score builder helpers ──────────────────────────────────────────

def normal_ml():
    """ML scores for a completely normal login."""
    return MLScores(xgb_prob=0.02, rf_prob=0.015, iso_score=0.12)

def attack_ml():
    """ML scores for a clear attacker."""
    return MLScores(xgb_prob=0.91, rf_prob=0.88, iso_score=0.82)

def normal_dna(match=0.94):
    return DNAScores(overall_match=match, drift_type="none", radar_scores={})

def attack_dna():
    return DNAScores(overall_match=0.07, drift_type="fast", radar_scores={})

def normal_graph():
    return GraphScores(risk_score=0.0, permission_ok=True, is_lateral=False)

def attack_graph():
    return GraphScores(risk_score=20.0, permission_ok=False, is_lateral=False)

def normal_ip(country="India", city="Mumbai"):
    return IPSignals(country=country, city=city, impossible_travel=0,
                     is_new_country=False, is_new_device=False)

def vpn_ip(country="Netherlands", city="Amsterdam"):
    """VPN exit node — different country but travel speed is fine."""
    return IPSignals(country=country, city=city, impossible_travel=0,
                     is_new_country=True, is_new_device=False,
                     distance_km=7200, speed_kmh=750)  # under 900 → not impossible

def attack_ip():
    return IPSignals(country="Russia", city="Moscow", impossible_travel=1,
                     is_new_country=True, is_new_device=True,
                     distance_km=7200, speed_kmh=14400)


print(f"\n{BOLD}{'='*58}{RESET}")
print(f"{BOLD}  Risk Engine Tests — Phase 7{RESET}")
print(f"{BOLD}  Realistic real-world scenarios{RESET}")
print(f"{BOLD}{'='*58}{RESET}")


# ── 1. Perfect normal login ────────────────────────────────────────
print(f"\n{BOLD}1. Perfect normal login — should ALLOW{RESET}")
r = engine.evaluate("u_bob", normal_ml(), normal_dna(), normal_graph(), normal_ip())
check("Decision = ALLOW",              r.decision == "ALLOW",  f"got {r.decision}")
check("Score < 30",                    r.final_score < 30,     f"{r.final_score:.1f}")
check("No boosters fired",             r.booster_points == 0)
check("DNA contribution is low",       r.dna_contribution < 5)
check("ML contribution is low",        r.ml_contribution < 8)
check("Returns RiskResult",            isinstance(r, RiskResult))
print(f"    score={r.final_score:.1f}  decision={r.decision}  boosters={r.booster_points}")
print(f"    {r.explanation}")


# ── 2. Clear attacker — should BLOCK ──────────────────────────────
print(f"\n{BOLD}2. Clear attacker (wrong country, new device, impossible travel) — BLOCK{RESET}")
r2 = engine.evaluate("u_bob", attack_ml(), attack_dna(), normal_graph(), attack_ip())
check("Decision = BLOCK",              r2.decision == "BLOCK",  f"got {r2.decision}")
check("Score > 75",                    r2.final_score > 75,     f"{r2.final_score:.1f}")
check("Impossible travel booster fired",
      any("impossible travel" in s for s in r2.signals_fired))
check("DNA fast drift booster fired",
      any("DNA" in s or "behavioural" in s for s in r2.signals_fired))
check("New country booster fired",
      any("new country" in s for s in r2.signals_fired))
check("New device booster fired",
      any("new device" in s for s in r2.signals_fired))
print(f"    score={r2.final_score:.1f}  decision={r2.decision}")
print(f"    signals: {r2.signals_fired}")
print(f"    {r2.explanation}")


# ── 3. VPN login — real user using VPN ────────────────────────────
print(f"\n{BOLD}3. Real user on VPN (different country, normal behaviour) — OTP{RESET}")
# User is connecting via VPN to Netherlands exit node.
# ML scores are normal (VPN traffic looks like normal traffic).
# DNA is good (same hour, same device — VPN doesn't change behaviour).
# Only signal: new country flag.
# Expected: OTP (verify it's really them, not full block)
r3 = engine.evaluate("u_bob", normal_ml(), normal_dna(0.88), normal_graph(), vpn_ip())
check("Decision is OTP or ALLOW",      r3.decision in ("OTP", "ALLOW"),  f"got {r3.decision}")
check("Score < 55 (not STEPUP)",       r3.final_score < 55,              f"{r3.final_score:.1f}")
check("NOT blocked (VPN user allowed)",r3.decision != "BLOCK")
check("New country booster fired",
      any("new country" in s for s in r3.signals_fired))
check("Impossible travel NOT fired",
      not any("impossible travel" in s for s in r3.signals_fired))
print(f"    score={r3.final_score:.1f}  decision={r3.decision}")
print(f"    VPN: {vpn_ip().country}, {vpn_ip().city}  speed={vpn_ip().speed_kmh} km/h (under 900)")
print(f"    signals: {r3.signals_fired}")
print(f"    {r3.explanation}")


# ── 4. Attacker with correct password + VPN ────────────────────────
print(f"\n{BOLD}4. Attacker using VPN to spoof normal location — still caught{RESET}")
# This is the key real-world test.
# Attacker: uses VPN to appear to come from India (user's home country).
# So impossible_travel = 0, is_new_country = False.
# BUT: ML catches unusual patterns, DNA shows massive mismatch.
attacker_spoof_ip = IPSignals(
    country="India", city="Mumbai",       # spoofed via VPN
    impossible_travel=0,                   # VPN makes travel look possible
    is_new_country=False,                  # looks like home country
    is_new_device=True,                    # different device fingerprint
    distance_km=0, speed_kmh=0,
)
r4 = engine.evaluate("u_bob", attack_ml(), attack_dna(), normal_graph(), attacker_spoof_ip)
check("Score > 55 despite VPN spoof",  r4.final_score > 55,  f"{r4.final_score:.1f}")
check("Blocked or STEPUP despite VPN", r4.decision in ("BLOCK","STEPUP"), f"{r4.decision}")
check("DNA drift caught the attacker",
      any("DNA" in s or "behavioural" in s for s in r4.signals_fired))
print(f"    score={r4.final_score:.1f}  decision={r4.decision}")
print(f"    VPN spoofed location but DNA+ML still caught it")
print(f"    signals: {r4.signals_fired}")


# ── 5. Permission violation ────────────────────────────────────────
print(f"\n{BOLD}5. Role permission violation (viewer accessing admin_panel) — BLOCK{RESET}")
r5 = engine.evaluate("u_viewer", normal_ml(), normal_dna(), attack_graph(), normal_ip())
check("Decision = BLOCK (hard rule)",  r5.decision == "BLOCK",  f"got {r5.decision}")
check("No-permission booster fired",
      any("permission" in s for s in r5.signals_fired))
check("Graph contribution > 0",        r5.graph_contribution > 0)
print(f"    score={r5.final_score:.1f}  decision={r5.decision}  graph_risk={r5.graph_risk}")
print(f"    signals: {r5.signals_fired}")


# ── 6. Borderline — slight off-hours, minor anomaly ───────────────
print(f"\n{BOLD}6. Borderline case — slight anomaly, should not over-react{RESET}")
r6 = engine.evaluate("u_bob",
    MLScores(xgb_prob=0.12, rf_prob=0.09, iso_score=0.28),
    DNAScores(overall_match=0.78, drift_type="none", radar_scores={}),
    normal_graph(),
    normal_ip(),
)
check("Score between 20–50 (borderline)", 15 < r6.final_score < 55, f"{r6.final_score:.1f}")
check("Not blocked (not enough evidence)", r6.decision != "BLOCK")
check("No boosters (no confirmed signals)",r6.booster_points == 0)
print(f"    score={r6.final_score:.1f}  decision={r6.decision}")
print(f"    {r6.explanation}")


# ── 7. Impossible travel — real VPN scenario ──────────────────────
print(f"\n{BOLD}7. Impossible travel — logged in from India, now from London in 20 min{RESET}")
# This simulates a REAL test: user uses VPN with an exit node
# far away from their last login. The travel speed exceeds 900 km/h.
imp_travel_ip = IPSignals(
    country="United Kingdom", city="London",
    impossible_travel=1,                          # 7192 km in 20 min
    is_new_country=True,
    is_new_device=False,                          # same device
    distance_km=7192, speed_kmh=21576,
)
r7 = engine.evaluate("u_bob", normal_ml(), normal_dna(0.85), normal_graph(), imp_travel_ip)
check("Score > 30 (impossible travel is serious)", r7.final_score > 30, f"{r7.final_score:.1f}")
check("Impossible travel booster fired",
      any("impossible travel" in s for s in r7.signals_fired))
check("Distance shown in signal",
      any("7192" in s or "km" in s for s in r7.signals_fired))
print(f"    score={r7.final_score:.1f}  decision={r7.decision}")
print(f"    Distance: {imp_travel_ip.distance_km:.0f} km  Speed: {imp_travel_ip.speed_kmh:.0f} km/h")
print(f"    signals: {r7.signals_fired}")


# ── 8. New user profile ────────────────────────────────────────────
print(f"\n{BOLD}8. New user — no DNA profile yet (first login){RESET}")
r8 = engine.evaluate("u_newuser",
    normal_ml(),
    DNAScores(overall_match=0.5, drift_type="none", is_new_profile=True, radar_scores={}),
    normal_graph(),
    normal_ip(),
)
check("Not blocked on first login",    r8.decision != "BLOCK")
check("Score reasonable (not 0)",      r8.final_score > 0)
check("Score not too high (<50)",      r8.final_score < 50, f"{r8.final_score:.1f}")
print(f"    score={r8.final_score:.1f}  decision={r8.decision}")
print(f"    New user gets neutral treatment until DNA profile builds up")


# ── 9. to_dict() for API response ────────────────────────────────
print(f"\n{BOLD}9. API response and Firestore serialisation{RESET}")
api_dict = r.to_dict()
fs_dict  = r.to_firestore_doc()

required_api = ["final_score","decision","score_breakdown","model_scores",
                "signals_fired","explanation","user_id","timestamp"]
required_fs  = ["user_id","final_score","decision","xgb_prob","rf_prob",
                "iso_score","dna_match","graph_risk","signals_fired","is_anomaly"]

for k in required_api:
    check(f"API dict has '{k}'", k in api_dict)
for k in required_fs:
    check(f"Firestore doc has '{k}'", k in fs_dict)
check("API dict JSON serialisable",   bool(json.dumps(api_dict)))
check("Firestore doc JSON serialisable", bool(json.dumps(fs_dict)))
check("is_anomaly = 0 for ALLOW",     fs_dict["is_anomaly"] == 0)

atk_fs = r2.to_firestore_doc()
check("is_anomaly = 1 for BLOCK",     atk_fs["is_anomaly"] == 1)

print(f"\n    Score breakdown for normal login:")
for k, v in api_dict["score_breakdown"].items():
    print(f"    {k:28s}: {v:.2f}")


# ── 10. Score component verification ─────────────────────────────
print(f"\n{BOLD}10. Score formula verification (weights sum correctly){RESET}")
# Test that weights add up correctly with known inputs
# xgb=1.0, rf=1.0, iso=1.0, dna=0.0 (mismatch), graph=25 (max)
r_max_ml = engine.evaluate("u_max",
    MLScores(xgb_prob=1.0, rf_prob=1.0, iso_score=1.0),
    DNAScores(overall_match=0.0, drift_type="none"),
    GraphScores(risk_score=25.0, permission_ok=True),
    IPSignals(country="X", impossible_travel=0),
)
check("Max ML+DNA+graph without boosters < 100",
      r_max_ml.final_score <= 100, f"{r_max_ml.final_score:.1f}")
check("All components contribute",
      r_max_ml.ml_contribution > 0 and
      r_max_ml.dna_contribution > 0 and
      r_max_ml.graph_contribution > 0)

# Test that perfect scores give near-zero risk
r_zero = engine.evaluate("u_zero",
    MLScores(xgb_prob=0.0, rf_prob=0.0, iso_score=0.0),
    DNAScores(overall_match=1.0, drift_type="none"),
    GraphScores(risk_score=0.0, permission_ok=True),
    IPSignals(country="India", impossible_travel=0),
)
check("Perfect scores → risk ≈ 0",     r_zero.final_score < 5, f"{r_zero.final_score:.2f}")
check("Perfect scores → ALLOW",        r_zero.decision == "ALLOW")
print(f"\n    Max inputs (no boosters):  {r_max_ml.final_score:.1f}")
print(f"    Perfect inputs:            {r_zero.final_score:.2f}")


# ── 11. VPN detection matrix ──────────────────────────────────────
print(f"\n{BOLD}11. VPN detection matrix — all combinations{RESET}")
print(f"\n    {'Scenario':38s}  {'Score':6s}  {'Decision':8s}  Blocked?")
print(f"    {'-'*70}")

vpn_scenarios = [
    ("Real user, no VPN, home country",
     normal_ml(), normal_dna(0.95), normal_graph(),
     IPSignals("India", "Mumbai", 0, False, False, 0, 0)),

    ("Real user, VPN, new country, normal behaviour",
     normal_ml(), normal_dna(0.88), normal_graph(),
     IPSignals("Germany", "Frankfurt", 0, True, False, 7200, 750)),

    ("Real user, VPN, impossible travel speed",
     normal_ml(), normal_dna(0.85), normal_graph(),
     IPSignals("UK", "London", 1, True, False, 7192, 21576)),

    ("Attacker, VPN spoofing home country",
     attack_ml(), attack_dna(), normal_graph(),
     IPSignals("India", "Mumbai", 0, False, True, 0, 0)),

    ("Attacker, no VPN, different country",
     attack_ml(), attack_dna(), normal_graph(),
     IPSignals("Russia", "Moscow", 1, True, True, 7192, 14383)),

    ("Attacker, VPN, permission violation",
     attack_ml(), attack_dna(), attack_graph(),
     IPSignals("Germany", "Berlin", 0, True, True, 7000, 700)),
]

for label, ml_s, dna_s, graph_s, ip_s in vpn_scenarios:
    rv = engine.evaluate("u_test", ml_s, dna_s, graph_s, ip_s)
    blocked = "YES" if rv.decision in ("BLOCK","STEPUP") else "no"
    print(f"    {label:38s}  {rv.final_score:5.1f}  {rv.decision:8s}  {blocked}")


# ── 12. quick_score convenience method ───────────────────────────
print(f"\n{BOLD}12. quick_score convenience method{RESET}")
score, dec = engine.quick_score(
    xgb_prob=0.02, rf_prob=0.01, iso_score=0.15,
    dna_match=0.94, graph_risk=0.0, country="India",
)
check("quick_score returns float",    isinstance(score, float))
check("quick_score returns string",   isinstance(dec, str))
check("Normal quick_score → ALLOW",   dec == "ALLOW",  f"got {dec}")
check("Normal quick_score < 30",      score < 30,      f"{score:.1f}")

score2, dec2 = engine.quick_score(
    xgb_prob=0.92, rf_prob=0.88, iso_score=0.85,
    dna_match=0.05, graph_risk=20.0,
    impossible_travel=1, is_new_country=True, is_new_device=True,
    distance_km=7192, speed_kmh=14383, country="Russia",
)
check("Attack quick_score → BLOCK",   dec2 == "BLOCK", f"got {dec2}")
check("Attack quick_score > 75",      score2 > 75,     f"{score2:.1f}")


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
