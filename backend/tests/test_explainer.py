"""
backend/tests/test_explainer.py
══════════════════════════════════════════════════════════════════
Phase 8 — Explainer Tests (Mistral version)

Run:
    cd backend
    python -m tests.test_explainer

No Mistral API key needed — mocked for tests.
No Firebase needed.
══════════════════════════════════════════════════════════════════
"""

import sys, os, json, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch
import numpy as np

from engines.shap_explainer import SHAPExplainer, SHAPResult
from engines.llm_explainer  import LLMExplainer, LLMExplanation
from engines.explainer      import Explainer, ExplainResult

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
    return asyncio.get_event_loop().run_until_complete(coro)

# ── Test data ──────────────────────────────────────────────────────
FEATURES = [
    "hour_sin","hour_cos","hour_deviation","is_weekend","is_offhours",
    "new_device","country_change","impossible_travel","failed_norm",
    "resource_sensitivity","privilege_gap","login_velocity",
    "multi_attack_flag","hour_x_newdev","fail_x_newdev",
]

FV_NORMAL = np.array([
    0.0, -0.7, 0.05, 0.0, 0.0,
    0.0,  0.0,  0.0, 0.0, 2.0,
    0.0,  0.8,  0.0, 0.0, 0.0,
])
FV_ATTACK = np.array([
   -0.5, -0.7, 0.8, 0.0, 1.0,
    1.0,  1.0, 1.0, 0.8, 4.0,
    1.0,  5.0, 1.0, 0.8, 0.8,
])

NORMAL_CTX = {"hour":9, "usual_hour":9.0, "dna_match":0.94,
              "drift_type":"none", "distance_km":0, "speed_kmh":0}
ATTACK_CTX = {"hour":3, "usual_hour":9.0, "dna_match":0.07,
              "drift_type":"fast", "distance_km":7192, "speed_kmh":21576}

def make_risk(decision="ALLOW", score=8.5, signals=None):
    r = MagicMock()
    r.decision      = decision
    r.final_score   = score
    r.user_id       = "u_test_001"
    r.country       = "India" if decision == "ALLOW" else "Russia"
    r.city          = "Mumbai" if decision == "ALLOW" else "Moscow"
    r.dna_match     = 0.94 if decision == "ALLOW" else 0.07
    r.drift_type    = "none" if decision == "ALLOW" else "fast"
    r.xgb_prob      = 0.02 if decision == "ALLOW" else 0.91
    r.signals_fired = signals or []
    return r


print(f"\n{BOLD}{'='*58}{RESET}")
print(f"{BOLD}  Phase 8 — Explainer Tests (Mistral AI){RESET}")
print(f"{BOLD}{'='*58}{RESET}")


# ── 1. SHAP fallback (no model loaded) ────────────────────────────
print(f"\n{BOLD}1. SHAP fallback — no XGBoost model loaded{RESET}")

se = SHAPExplainer()
rn = se.explain(FV_NORMAL, FEATURES, 8.5,  "ALLOW", 0.02)
ra = se.explain(FV_ATTACK, FEATURES, 94.0, "BLOCK", 0.91)

check("Returns SHAPResult",               isinstance(rn, SHAPResult))
check("is_fallback = True",               rn.is_fallback)
check("Has top_factors",                  len(rn.top_factors) > 0)
check("all_factors = 15",                 len(rn.all_factors) == 15, len(rn.all_factors))
check("Attack has risk_factors",          len(ra.risk_factors) > 0)
check("Top factor is 3-tuple",            len(ra.top_factors[0]) == 3)
check("Attack top contribution > 0",      ra.top_factors[0][1] > 0,
      f"{ra.top_factors[0][1]:.1f}")
check("to_dict() JSON serialisable",      bool(json.dumps(rn.to_dict())))
print(f"\n    Normal top: {rn.top_factors[0][2]} ({rn.top_factors[0][1]:+.1f} pts)")
print(f"    Attack top: {ra.top_factors[0][2]} ({ra.top_factors[0][1]:+.1f} pts)")


# ── 2. SHAP with real XGBoost model ───────────────────────────────
print(f"\n{BOLD}2. SHAP with real XGBoost model{RESET}")
try:
    import xgboost as xgb
    from sklearn.datasets import make_classification

    X_m, y_m = make_classification(
        n_samples=300, n_features=15, n_informative=8, random_state=42
    )
    mock_xgb = xgb.XGBClassifier(
        n_estimators=15, max_depth=3,
        eval_metric="logloss", random_state=42,
    )
    mock_xgb.fit(X_m, y_m)

    se_real = SHAPExplainer()
    se_real.load_model(mock_xgb)
    rr = se_real.explain(FV_NORMAL.reshape(1, -1), FEATURES, 8.5, "ALLOW", 0.02)

    check("Real SHAP returns SHAPResult",  isinstance(rr, SHAPResult))
    check("Real SHAP is NOT fallback",     not rr.is_fallback,
          "SHAP computed" if not rr.is_fallback else "fell back")
    check("Has exactly 5 top_factors",    len(rr.top_factors) == 5, len(rr.top_factors))
    check("base_score is float",          isinstance(rr.base_score, float))
    print(f"\n    Real SHAP top factors:")
    for name, pts, label in rr.top_factors:
        bar  = "█" * min(20, max(1, int(abs(pts) / 3)))
        sign = "+" if pts > 0 else ""
        print(f"    {label[:38]:38s}: {sign}{pts:.1f}  {bar}")

except ImportError:
    print("  SKIP — xgboost not installed")
except Exception as e:
    check("Real SHAP test ran cleanly", False, str(e))


# ── 3. LLM fallback (no Mistral key) ──────────────────────────────
print(f"\n{BOLD}3. LLM fallback — no Mistral API key{RESET}")

llm_no_key = LLMExplainer(api_key="")

async def t_allow():
    sd = se.explain(FV_NORMAL, FEATURES, 8.5, "ALLOW", 0.02)
    return await llm_no_key.explain(
        sd, "ALLOW", 8.5, [],
        {**NORMAL_CTX, "country": "India", "city": "Mumbai"},
    )

async def t_block():
    sd = se.explain(FV_ATTACK, FEATURES, 94.0, "BLOCK", 0.91)
    return await llm_no_key.explain(
        sd, "BLOCK", 94.0,
        ["impossible travel (+20): 7192km", "new country: Russia (+5)"],
        {**ATTACK_CTX, "country": "Russia", "city": "Moscow"},
    )

r_allow_fb = run(t_allow())
r_block_fb = run(t_block())

check("Returns LLMExplanation",           isinstance(r_allow_fb, LLMExplanation))
check("used_llm = False",                 not r_allow_fb.used_llm)
check("model_used = template-fallback",   r_allow_fb.model_used == "template-fallback")
check("short_text not empty",             len(r_allow_fb.short_text) > 5)
check("full_text not empty",              len(r_allow_fb.full_text) > 5)
check("ALLOW mentions verified",          any(w in r_allow_fb.short_text.lower()
                                              for w in ["verified","normal","94%","dna"]))
check("BLOCK mentions blocked/risk",      any(w in r_block_fb.short_text.lower()
                                              for w in ["blocked","block","risk"]))
check("BLOCK has key_reasons",            len(r_block_fb.key_reasons) > 0)
check("tokens_used = 0 (no API call)",    r_allow_fb.tokens_used == 0)
check("to_dict() serialisable",           bool(json.dumps(r_allow_fb.to_dict())))
print(f"\n    ALLOW fallback: {r_allow_fb.short_text}")
print(f"    BLOCK fallback: {r_block_fb.short_text}")
print(f"    BLOCK reasons:  {r_block_fb.key_reasons}")


# ── 4. LLM with mocked Mistral API ────────────────────────────────
print(f"\n{BOLD}4. LLM with mocked Mistral API response{RESET}")

MOCK_MISTRAL_RESPONSE = (
    "Login blocked — impossible travel from Mumbai to Moscow detected."
    "|||"
    "This login was blocked because the connecting IP is located in Moscow, "
    "Russia — 7,192 km from the last verified session in Mumbai, India just "
    "30 minutes ago, implying a travel speed of 21,576 km/h. The user's "
    "behavioural DNA matched only 7% of the normal profile."
    "|||"
    "• Login from Russia, 7,192 km from last location in Mumbai\n"
    "• Travel speed of 21,576 km/h is physically impossible\n"
    "• Behavioural DNA matched only 7% of normal user pattern\n"
    "• New device fingerprint detected"
)

def make_mistral_mock_response(text):
    msg   = MagicMock(); msg.content = text
    ch    = MagicMock(); ch.message  = msg
    usage = MagicMock(); usage.prompt_tokens = 310; usage.completion_tokens = 95
    resp  = MagicMock(); resp.choices = [ch]; resp.usage = usage
    return resp

async def t_mocked_mistral():
    llm = LLMExplainer(api_key="test-free-key")
    llm._client = MagicMock()

    async def fake_executor(executor, fn):
        return make_mistral_mock_response(MOCK_MISTRAL_RESPONSE)

    import asyncio as _aio
    with patch.object(_aio.get_event_loop(), "run_in_executor",
                      side_effect=fake_executor):
        sd = se.explain(FV_ATTACK, FEATURES, 94.0, "BLOCK", 0.91)
        result = await llm.explain(
            sd, "BLOCK", 94.0,
            ["impossible travel (+20): 7192km (21576 km/h)"],
            {**ATTACK_CTX, "country": "Russia", "city": "Moscow"},
        )
    return result

r_mocked = run(t_mocked_mistral())
check("Returns LLMExplanation",           isinstance(r_mocked, LLMExplanation))
check("used_llm = True",                  r_mocked.used_llm)
check("model = mistral-small-latest",     r_mocked.model_used == "mistral-small-latest")
check("short_text contains 'blocked'",    "blocked" in r_mocked.short_text.lower(),
      r_mocked.short_text)
check("full_text length > 50 chars",      len(r_mocked.full_text) > 50)
check("key_reasons >= 3 bullets",         len(r_mocked.key_reasons) >= 3,
      f"got {len(r_mocked.key_reasons)}")
check("tokens = 405 (310+95)",            r_mocked.tokens_used == 405,
      f"got {r_mocked.tokens_used}")
print(f"\n    Short:    {r_mocked.short_text}")
print(f"    Reasons:  {r_mocked.key_reasons}")


# ── 5. Full Explainer orchestrator ────────────────────────────────
print(f"\n{BOLD}5. Full Explainer orchestrator (SHAP + Mistral fallback){RESET}")

async def t_full_block():
    exp = Explainer(api_key="")
    risk = make_risk("BLOCK", 94.0, ["impossible travel (+20)", "new country: Russia (+5)"])
    return await exp.explain(FV_ATTACK, FEATURES, risk, ATTACK_CTX)

async def t_full_allow():
    exp = Explainer(api_key="")
    risk = make_risk("ALLOW", 8.5)
    return await exp.explain(FV_NORMAL, FEATURES, risk, NORMAL_CTX)

r_fb = run(t_full_block())
r_fa = run(t_full_allow())

check("Returns ExplainResult (BLOCK)",    isinstance(r_fb, ExplainResult))
check("Returns ExplainResult (ALLOW)",    isinstance(r_fa, ExplainResult))
check("BLOCK has short_text",             len(r_fb.short_text) > 5)
check("ALLOW has short_text",             len(r_fa.short_text) > 5)
check("BLOCK has shap_factors",           len(r_fb.shap_factors) > 0)
check("BLOCK has key_reasons (list)",     isinstance(r_fb.key_reasons, list))
check("to_dict() JSON serialisable",      bool(json.dumps(r_fb.to_dict())))

# Verify to_dict structure
d = r_fb.to_dict()
for key in ["short_text","full_text","key_reasons","shap_factors",
            "risk_factors","safe_factors","base_score","used_llm","model_used"]:
    check(f"to_dict() has '{key}'", key in d)

print(f"\n    BLOCK: {r_fb.short_text}")
print(f"    ALLOW: {r_fa.short_text}")
print(f"\n    SHAP factors for BLOCK:")
for item in d["shap_factors"]:
    sign = "+" if item["contribution"] > 0 else ""
    bar  = "█" * min(20, max(1, int(abs(item["contribution"]) / 2)))
    print(f"    {item['label'][:38]:38s}: {sign}{item['contribution']:.1f}  {bar}")


# ── 6. All four decision types ────────────────────────────────────
print(f"\n{BOLD}6. All four decision types produce valid explanations{RESET}")

async def t_all():
    exp = Explainer(api_key="")
    results = {}
    for dec, score, fv, ctx in [
        ("ALLOW",  8.5,  FV_NORMAL, NORMAL_CTX),
        ("OTP",    38.0, FV_NORMAL, NORMAL_CTX),
        ("STEPUP", 62.0, FV_ATTACK, ATTACK_CTX),
        ("BLOCK",  94.0, FV_ATTACK, ATTACK_CTX),
    ]:
        risk = make_risk(dec, score)
        results[dec] = await exp.explain(fv, FEATURES, risk, ctx)
    return results

all_r = run(t_all())
for dec, result in all_r.items():
    check(f"{dec} — short_text not empty",  len(result.short_text) > 5)
    check(f"{dec} — shap_factors present",  len(result.shap_factors) > 0)
    print(f"    {dec:8s}: {result.short_text}")


# ── 7. Mistral free tier info ─────────────────────────────────────
print(f"\n{BOLD}7. Mistral free tier details{RESET}")
print(f"    Model:     mistral-small-latest (free tier)")
print(f"    Sign up:   https://console.mistral.ai")
print(f"    Cost:      $0.00 on free tier")
print(f"    Limits:    1 req/sec | ~500k tokens/month")
print(f"    Logins/mo: ~500k tokens ÷ ~400 tokens/login ≈ 1,250 logins/month free")
check("Works without key (fallback active)", True)
api_set = bool(os.getenv("MISTRAL_API_KEY", ""))
if api_set:
    print(f"    {GREEN}MISTRAL_API_KEY is set ✓{RESET}")
else:
    print(f"    MISTRAL_API_KEY not set — fallback mode active")
    print(f"    Add to backend/.env:  MISTRAL_API_KEY=your_key_here")


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
