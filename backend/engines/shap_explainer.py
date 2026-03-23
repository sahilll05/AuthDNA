"""
backend/engines/shap_explainer.py
══════════════════════════════════════════════════════════════════
Phase 8 — SHAP Feature Importance Explainer

WHAT IS SHAP?
─────────────
SHAP (SHapley Additive exPlanations) answers:
"How much did each feature contribute to this specific prediction?"

Example output for a BLOCK decision:
  new_device         → +31.2 points  (pushed score UP toward BLOCK)
  impossible_travel  → +28.4 points  (pushed score UP)
  hour_deviation     → +22.1 points  (pushed score UP — logged in at 3am)
  country_change     → +18.6 points  (pushed score UP)
  failed_norm        → -2.1  points  (pushed score DOWN — no failed attempts)

These numbers go to llm_explainer.py which converts them to plain English.

USAGE:
──────
  from engines.shap_explainer import SHAPExplainer

  explainer = SHAPExplainer()
  explainer.load_model(xgb_model)      # call once at startup

  result = explainer.explain(
      feature_vector = np.array([...]),
      feature_names  = FEATURES,
      risk_score     = 87.3,
      decision       = "BLOCK",
  )
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Optional

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    print("[SHAPExplainer] shap not installed. Run: pip install shap")


# ── Human-readable labels for feature names ───────────────────────
FEATURE_LABELS = {
    "hour_sin":            "login time (cyclical)",
    "hour_cos":            "login time (cyclical)",
    "hour_deviation":      "login hour vs usual hour",
    "is_weekend":          "weekend login",
    "is_offhours":         "off-hours login (before 6am or after 10pm)",
    "new_device":          "new/unknown device",
    "country_change":      "different country from usual",
    "impossible_travel":   "physically impossible travel speed",
    "failed_norm":         "failed login attempts",
    "resource_sensitivity":"resource sensitivity level",
    "privilege_gap":       "clearance vs resource sensitivity gap",
    "login_velocity":      "login frequency",
    "multi_attack_flag":   "simultaneous new device + new country",
    "hour_x_newdev":       "off-hours on new device",
    "fail_x_newdev":       "failed attempts on new device",
}

HIGH_IS_SUSPICIOUS = {
    "hour_deviation", "is_offhours", "new_device", "country_change",
    "impossible_travel", "failed_norm", "privilege_gap",
    "multi_attack_flag", "hour_x_newdev", "fail_x_newdev", "login_velocity",
}

SHAP_SCALE_FACTOR = 100.0


# ══════════════════════════════════════════════════════════════════
# DATA CLASS
# ══════════════════════════════════════════════════════════════════

@dataclass
class SHAPResult:
    """Output of SHAPExplainer.explain() for one login."""

    # Top factors sorted by absolute contribution — (name, pts, label)
    top_factors:     list  = field(default_factory=list)
    all_factors:     list  = field(default_factory=list)
    risk_factors:    list  = field(default_factory=list)  # pushed score UP
    safe_factors:    list  = field(default_factory=list)  # pushed score DOWN

    base_score:      float = 0.0
    xgb_probability: float = 0.0
    risk_score:      float = 0.0
    decision:        str   = ""
    is_fallback:     bool  = False

    def to_dict(self) -> dict:
        return {
            "top_factors":     self.top_factors,
            "risk_factors":    self.risk_factors,
            "safe_factors":    self.safe_factors,
            "base_score":      round(self.base_score, 2),
            "xgb_probability": round(self.xgb_probability, 4),
            "risk_score":      round(self.risk_score, 2),
            "decision":        self.decision,
            "is_fallback":     self.is_fallback,
        }


# ══════════════════════════════════════════════════════════════════
# SHAP EXPLAINER
# ══════════════════════════════════════════════════════════════════

class SHAPExplainer:
    """
    Wraps SHAP TreeExplainer for XGBoost.
    TreeExplainer is exact (not approximated) for tree-based models
    and 100–1000x faster than KernelExplainer.
    """

    def __init__(self):
        self._explainer = None
        self._model     = None

    def load_model(self, xgb_model) -> None:
        """
        Initialise SHAP with the trained XGBoost model.
        Call ONCE at FastAPI startup — not per request.
        """
        if not SHAP_AVAILABLE:
            print("[SHAPExplainer] SHAP not available — will use fallback")
            return
        try:
            self._model     = xgb_model
            self._explainer = shap.TreeExplainer(
                xgb_model,
                feature_perturbation="auto",
            )
            print("[SHAPExplainer] TreeExplainer initialised successfully")
        except Exception as e:
            print(f"[SHAPExplainer] Could not initialise TreeExplainer: {e}")
            self._explainer = None

    def explain(
        self,
        feature_vector:  np.ndarray,
        feature_names:   list[str],
        risk_score:      float,
        decision:        str,
        xgb_probability: float = 0.0,
        top_n:           int   = 5,
    ) -> SHAPResult:
        """
        Compute SHAP feature contributions for one login.

        Args:
            feature_vector:  15-element numpy array (already scaled)
            feature_names:   list matching the vector order
            risk_score:      final risk score 0–100
            decision:        ALLOW/OTP/STEPUP/BLOCK
            xgb_probability: raw XGBoost attack probability
            top_n:           number of top factors to return

        Returns:
            SHAPResult with contributions in risk-score points
        """
        if self._explainer is None or not SHAP_AVAILABLE:
            return self._fallback_explain(
                feature_vector, feature_names, risk_score, decision, xgb_probability
            )
        try:
            return self._shap_explain(
                feature_vector, feature_names, risk_score, decision, xgb_probability, top_n
            )
        except Exception as e:
            print(f"[SHAPExplainer] SHAP failed: {e} — using fallback")
            return self._fallback_explain(
                feature_vector, feature_names, risk_score, decision, xgb_probability
            )

    def _shap_explain(self, fv, feature_names, risk_score, decision, xgb_prob, top_n):
        fv_2d = fv.reshape(1, -1) if fv.ndim == 1 else fv
        shap_values = self._explainer.shap_values(fv_2d)

        # Handle different SHAP output formats
        if isinstance(shap_values, list):
            sv = shap_values[1][0]
        elif len(shap_values.shape) == 3:
            sv = shap_values[0, :, 1]
        else:
            sv = shap_values[0]

        # Base value
        try:
            base_val = float(self._explainer.expected_value)
            if isinstance(self._explainer.expected_value, (list, np.ndarray)):
                base_val = float(self._explainer.expected_value[1])
        except Exception:
            base_val = 0.5

        base_score_pts = float(np.clip(base_val * SHAP_SCALE_FACTOR, 0, 100))

        all_factors = []
        for i, name in enumerate(feature_names):
            if i >= len(sv):
                continue
            shap_val = float(sv[i])
            pts      = shap_val * SHAP_SCALE_FACTOR
            label    = FEATURE_LABELS.get(name, name.replace("_", " "))
            all_factors.append({
                "feature":      name,
                "label":        label,
                "shap_value":   round(shap_val, 4),
                "contribution": round(pts, 2),
                "direction":    "risk" if pts > 0 else "safe",
            })

        all_factors.sort(key=lambda x: abs(x["contribution"]), reverse=True)
        top_simple   = [(f["feature"], f["contribution"], f["label"])
                        for f in all_factors[:top_n]]
        risk_factors = [f for f in all_factors if f["contribution"] > 0.5]
        safe_factors = [f for f in all_factors if f["contribution"] < -0.5]

        return SHAPResult(
            top_factors=top_simple, all_factors=all_factors,
            risk_factors=risk_factors, safe_factors=safe_factors,
            base_score=base_score_pts, xgb_probability=xgb_prob,
            risk_score=risk_score, decision=decision, is_fallback=False,
        )

    def _fallback_explain(self, fv, feature_names, risk_score, decision, xgb_prob):
        """Rule-based fallback when SHAP is unavailable."""
        fv_flat     = fv.flatten()
        all_factors = []

        for i, name in enumerate(feature_names):
            if i >= len(fv_flat):
                continue
            val   = float(fv_flat[i])
            label = FEATURE_LABELS.get(name, name.replace("_", " "))

            if name in HIGH_IS_SUSPICIOUS:
                if name in {"new_device","country_change","impossible_travel",
                             "multi_attack_flag","is_offhours","is_weekend"}:
                    pts = val * 20.0
                elif name == "failed_norm":
                    pts = val * 30.0
                elif name == "hour_deviation":
                    pts = val * 25.0
                elif name == "privilege_gap":
                    pts = val * 10.0
                else:
                    pts = val * 5.0
            else:
                pts = 0.0

            all_factors.append({
                "feature": name, "label": label,
                "shap_value": round(val, 4), "contribution": round(pts, 2),
                "direction": "risk" if pts > 0 else "safe",
            })

        all_factors.sort(key=lambda x: abs(x["contribution"]), reverse=True)
        top_simple   = [(f["feature"], f["contribution"], f["label"])
                        for f in all_factors[:5]]
        risk_factors = [f for f in all_factors if f["contribution"] > 0.5]
        safe_factors = [f for f in all_factors if f["contribution"] < -0.5]

        return SHAPResult(
            top_factors=top_simple, all_factors=all_factors,
            risk_factors=risk_factors, safe_factors=safe_factors,
            base_score=5.0, xgb_probability=xgb_prob,
            risk_score=risk_score, decision=decision, is_fallback=True,
        )
