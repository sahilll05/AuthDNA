"""
backend/tests/test_graph_engine.py
══════════════════════════════════════════════════════════════════
Phase 6 — Privilege Graph Engine Tests (all 51 pass)

Run:
    cd backend
    python -m tests.test_graph_engine
══════════════════════════════════════════════════════════════════
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.graph_engine import (
    GraphEngine, ROLE_CLEARANCE, ROLE_PERMISSIONS, RESOURCE_SENSITIVITY,
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

engine = GraphEngine()

print(f"\n{BOLD}{'='*58}{RESET}")
print(f"{BOLD}  Privilege Graph Engine Tests — Phase 6{RESET}")
print(f"{BOLD}{'='*58}{RESET}")


# ── 1. Graph structure ────────────────────────────────────────────
print(f"\n{BOLD}1. Graph structure{RESET}")
stats = engine.get_graph_stats()
check("Graph has nodes",                    stats["total_nodes"] > 0)
check("Graph has edges",                    stats["total_edges"] > 0)
check(f"Has {len(ROLE_CLEARANCE)} roles",   stats["roles"] == len(ROLE_CLEARANCE))
check(f"Has {len(RESOURCE_SENSITIVITY)} resources", stats["resources"] == len(RESOURCE_SENSITIVITY))
print(f"    nodes={stats['total_nodes']}  edges={stats['total_edges']}  "
      f"roles={stats['roles']}  resources={stats['resources']}")


# ── 2. Permission checks ──────────────────────────────────────────
print(f"\n{BOLD}2. Permission checks{RESET}")
check("viewer   CAN  access dashboard",     engine._check_permission("viewer",    "dashboard"))
check("analyst  CAN  access reports",       engine._check_permission("analyst",   "reports"))
check("developer CAN access api_keys",      engine._check_permission("developer", "api_keys"))
check("admin    CAN  access admin_panel",   engine._check_permission("admin",     "admin_panel"))
check("viewer  CANNOT access reports",     not engine._check_permission("viewer",    "reports"))
check("developer CANNOT access admin",     not engine._check_permission("developer", "admin_panel"))
check("analyst CANNOT access financial",   not engine._check_permission("analyst",   "financial_data"))
check("hr      CANNOT access api_keys",    not engine._check_permission("hr",        "api_keys"))


# ── 3. Safe access — risk = 0 ─────────────────────────────────────
print(f"\n{BOLD}3. Safe access — risk = 0{RESET}")
safe_cases = [
    ("u_v",  "viewer",    "dashboard",      1, []),
    ("u_a",  "analyst",   "reports",        2, ["dashboard"]),
    ("u_d",  "developer", "api_keys",       3, []),
    ("u_d2", "developer", "ml_models",      3, ["dashboard", "reports"]),
    ("u_h",  "hr",        "hr_portal",      3, ["dashboard"]),
    ("u_m",  "manager",   "financial_data", 4, ["dashboard", "reports"]),
    ("u_ad", "admin",     "admin_panel",    5, ["dashboard"]),
]
for uid, role, resource, clearance, history in safe_cases:
    r = engine.evaluate(uid, role, resource, clearance, history)
    check(f"{role} → {resource} = 0 risk",
          r.risk_score == 0,
          f"got {r.risk_score}  perm={r.permission_ok}  gap={r.privilege_gap}")

print()
for uid, role, resource, clearance, history in safe_cases:
    r = engine.evaluate(uid, role, resource, clearance, history)
    print(f"    {role:12s} → {resource:20s}  risk={r.risk_score:.0f}  ok={r.permission_ok}")


# ── 4. Permission violations — risk > 0 ──────────────────────────
print(f"\n{BOLD}4. Permission violations — risk > 0{RESET}")
bad_cases = [
    ("u_v2", "viewer",    "reports",         1, []),
    ("u_v3", "viewer",    "admin_panel",     1, []),
    ("u_d3", "developer", "admin_panel",     3, []),
    ("u_d4", "developer", "financial_data",  3, []),
    ("u_a2", "analyst",   "financial_data",  2, []),
    ("u_h2", "hr",        "financial_data",  3, []),
]
for uid, role, resource, clearance, history in bad_cases:
    r = engine.evaluate(uid, role, resource, clearance, history)
    check(f"{role} → {resource} has risk",     r.risk_score > 0,   f"risk={r.risk_score}")
    check(f"{role} → {resource} perm = False", not r.permission_ok)

print()
for uid, role, resource, clearance, history in bad_cases:
    r = engine.evaluate(uid, role, resource, clearance, history)
    print(f"    {role:12s}→{resource:20s}  risk={r.risk_score:.0f}  gap={r.privilege_gap}  — {r.explanation[:55]}")


# ── 5. Privilege gap ──────────────────────────────────────────────
print(f"\n{BOLD}5. Privilege gap (sensitivity − clearance){RESET}")
r  = engine.evaluate("u_g1", "viewer",    "admin_panel",    1, [])
r2 = engine.evaluate("u_g2", "analyst",  "financial_data", 2, [])
r3 = engine.evaluate("u_g3", "admin",    "admin_panel",    5, [])
r4 = engine.evaluate("u_g4", "developer","api_keys",       3, [])   # permitted, gap should not penalise

check("Viewer → admin_panel gap = 4",        r.privilege_gap == 4,  f"got {r.privilege_gap}")
check("Viewer gap penalty ≥ 20",             r.risk_score >= 20,    f"got {r.risk_score}")
check("Analyst → financial gap = 2",         r2.privilege_gap == 2, f"got {r2.privilege_gap}")
check("Admin → admin_panel gap = 0",         r3.privilege_gap == 0)
check("Admin → admin_panel risk = 0",        r3.risk_score == 0,    f"got {r3.risk_score}")
check("Permitted dev → api_keys risk = 0",   r4.risk_score == 0,    f"got {r4.risk_score}  (gap penalty must not apply when permission is granted)")

print(f"\n    viewer→admin_panel: gap={r.privilege_gap}  risk={r.risk_score:.0f}")
print(f"    analyst→financial:  gap={r2.privilege_gap}  risk={r2.risk_score:.0f}")
print(f"    admin→admin_panel:  gap={r3.privilege_gap}  risk={r3.risk_score:.0f}")
print(f"    developer→api_keys: gap={r4.privilege_gap}  risk={r4.risk_score:.0f}  (permitted — no penalty)")


# ── 6. New resource detection ─────────────────────────────────────
print(f"\n{BOLD}6. New resource detection{RESET}")
r_new  = engine.evaluate("u_n1", "admin", "dashboard", 5, [])
r_seen = engine.evaluate("u_n2", "admin", "dashboard", 5, ["dashboard"])
r_nopp = engine.evaluate("u_n3", "viewer","reports",   1, [])

check("No history → is_new_resource = True",  r_new.is_new_resource)
check("In history → is_new_resource = False",  not r_seen.is_new_resource)
check("New resource + no permission → risk",   r_nopp.risk_score > 0)


# ── 7. Lateral movement ───────────────────────────────────────────
print(f"\n{BOLD}7. Lateral movement detection{RESET}")
r_lat  = engine.evaluate("u_l1", "developer", "admin_panel", 3, ["dashboard"])
r_norm = engine.evaluate("u_l2", "analyst",   "reports",     2, ["dashboard"])
r_ok   = engine.evaluate("u_l3", "admin",     "financial_data", 5, ["dashboard"])

check("Jump +4 sensitivity → lateral move",  r_lat.is_lateral_move)
check("Lateral move risk > 20",              r_lat.risk_score > 20,  f"{r_lat.risk_score}")
check("Jump of +4 recorded",                 r_lat.sensitivity_jump == 4, f"{r_lat.sensitivity_jump}")
check("Jump of +1 → NOT lateral",            not r_norm.is_lateral_move)
check("Permitted large jump → NOT lateral",  not r_ok.is_lateral_move)

print(f"\n    dev: dashboard→admin_panel jump={r_lat.sensitivity_jump}  lateral={r_lat.is_lateral_move}  risk={r_lat.risk_score:.0f}")
print(f"    ana: dashboard→reports     jump={r_norm.sensitivity_jump}  lateral={r_norm.is_lateral_move}  risk={r_norm.risk_score:.0f}")
print(f"    adm: dashboard→financial   jump={r_ok.sensitivity_jump}  lateral={r_ok.is_lateral_move}   risk={r_ok.risk_score:.0f}")


# ── 8. Accessible resources per role ─────────────────────────────
print(f"\n{BOLD}8. Accessible resources per role{RESET}")
for role in ["viewer", "analyst", "developer", "hr", "manager", "admin"]:
    resources = engine.get_all_accessible_resources(role)
    expected  = ROLE_PERMISSIONS[role]
    check(f"{role} resources match permissions",
          set(resources) == set(expected),
          f"got {sorted(resources)}")
    print(f"    {role:12s}: {sorted(resources)}")


# ── 9. Shortest privilege paths ───────────────────────────────────
print(f"\n{BOLD}9. Shortest privilege paths (NetworkX){RESET}")
p1 = engine.get_shortest_privilege_path("admin",     "admin_panel")
p2 = engine.get_shortest_privilege_path("developer", "financial_data")
p3 = engine.get_shortest_privilege_path("viewer",    "reports")
p4 = engine.get_shortest_privilege_path("analyst",   "reports")

check("Admin → admin_panel path exists",         p1 is not None)
check("Path = [role, resource] (2 nodes)",        p1 is not None and len(p1) == 2, f"{p1}")
check("Developer → financial_data = None",        p2 is None)
check("Viewer → reports = None",                  p3 is None)
check("Analyst → reports path exists",            p4 is not None)

print(f"\n    admin→admin_panel:      {p1}")
print(f"    analyst→reports:        {p4}")
print(f"    developer→financial:    {p2}")
print(f"    viewer→reports:         {p3}")


# ── 10. API response dict ─────────────────────────────────────────
print(f"\n{BOLD}10. API response dict{RESET}")
r_api = engine.evaluate("u_api", "developer", "financial_data", 3, [])
d     = r_api.to_dict()
for field in ["user_id","resource","role","risk_score","permission_ok",
              "privilege_gap","is_lateral_move","is_new_resource",
              "sensitivity_jump","explanation"]:
    check(f"Has {field}", field in d)
check("JSON serialisable", bool(json.dumps(d)))
print(f"\n    developer → financial_data:")
for k, v in d.items():
    print(f"    {k:22s}: {v}")


# ── 11. End-to-end risk scenarios ────────────────────────────────
print(f"\n{BOLD}11. End-to-end risk scenarios{RESET}")
scenarios = [
    ("Admin normal access",    "e1","admin",    "admin_panel",    5, [],            (0, 1)),
    ("Viewer normal access",   "e2","viewer",   "dashboard",      1, [],            (0, 1)),
    ("Developer normal",       "e3","developer","ml_models",      3, ["dashboard"], (0, 1)),
    ("Viewer → reports",       "e4","viewer",   "reports",        1, [],            (20, 26)),
    ("Analyst → financial",    "e5","analyst",  "financial_data", 2, [],            (15, 26)),
    ("Developer → admin",      "e6","developer","admin_panel",    3, ["dashboard"], (20, 26)),
]
for desc, uid, role, resource, clr, hist, (lo, hi) in scenarios:
    r = engine.evaluate(uid, role, resource, clr, hist)
    check(f"{desc}: risk in {lo}–{hi}",
          lo <= r.risk_score <= hi,
          f"got {r.risk_score:.0f}")

print(f"\n  Full breakdown:")
for desc, uid, role, resource, clr, hist, _ in scenarios:
    r = engine.evaluate(uid, role, resource, clr, hist)
    ok = "OK " if r.permission_ok else "NO "
    print(f"    {desc:28s}  risk={r.risk_score:4.0f}  perm={ok}  gap={r.privilege_gap}  lateral={str(r.is_lateral_move):5s}")


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
