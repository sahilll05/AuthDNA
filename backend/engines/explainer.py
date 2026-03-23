"""
backend/engines/explainer.py
══════════════════════════════════════════════════════════════════
Phase 8 — Explainer Orchestrator

Single entry point that Phase 10 imports.
Runs SHAP → Mistral → returns ExplainResult.

USAGE (Phase 10 FastAPI):
─────────────────────────
  from engines.explainer import Explainer

  # At startup (once):
  explainer = Explainer()
  explainer.setup(xgb_model=xgb_model)

  # Per login:
  explanation = await explainer.explain(
      feature_vector = fv_scaled,
      feature_names  = meta["features"],
      risk_result    = risk_result,
      context        = {
          "hour":        hour,
          "usual_hour":  user_data["usual_hour_mean"],
          "dna_match":   dna_result.overall_score,
          "drift_type":  dna_result.drift_type,
          "distance_km": ip_result.distance_km,
          "speed_kmh":   ip_result.speed_kmh,
      },
  )

  # Add to API response:
  response["explanation"] = explanation.to_dict()
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import os
import asyncio
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from engines.shap_explainer import SHAPExplainer, SHAPResult
from engines.llm_explainer  import LLMExplainer, LLMExplanation


# ══════════════════════════════════════════════════════════════════
# COMBINED RESULT
# ══════════════════════════════════════════════════════════════════

@dataclass
class ExplainResult:
    """
    Complete explanation for one login.
    Contains both SHAP data (for the bar chart) and
    Mistral text (for the explanation panel).
    """
    # ── Mistral-generated text ────────────────────────────────
    short_text:   str    # 1 sentence — shown under the risk gauge
    full_text:    str    # 2–3 sentences — shown in the panel
    key_reasons:  list   # bullet points

    # ── SHAP data (drives the bar chart in React) ─────────────
    shap_factors: list   # top 5 [(feature, pts, label)]
    risk_factors: list   # positive SHAP (pushed score UP)
    safe_factors: list   # negative SHAP (pushed score DOWN)
    base_score:   float  # expected score for average user

    # ── Meta ──────────────────────────────────────────────────
    used_llm:     bool
    model_used:   str
    tokens_used:  int
    is_fallback:  bool

    def to_dict(self) -> dict:
        """Full dict for the /evaluate-login API response."""
        return {
            "short_text":   self.short_text,
            "full_text":    self.full_text,
            "key_reasons":  self.key_reasons,
            "shap_factors": [
                {
                    "feature":      f,
                    "contribution": round(pts, 2),
                    "label":        label,
                    "direction":    "risk" if pts > 0 else "safe",
                }
                for f, pts, label in self.shap_factors
            ],
            "risk_factors": [
                {
                    "feature":      f["feature"],
                    "label":        f["label"],
                    "contribution": round(f["contribution"], 2),
                }
                for f in self.risk_factors[:5]
            ],
            "safe_factors": [
                {
                    "feature":      f["feature"],
                    "label":        f["label"],
                    "contribution": round(f["contribution"], 2),
                }
                for f in self.safe_factors[:3]
            ],
            "base_score":   round(self.base_score, 2),
            "used_llm":     self.used_llm,
            "model_used":   self.model_used,
            "tokens_used":  self.tokens_used,
        }


# ══════════════════════════════════════════════════════════════════
# EXPLAINER ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════

class Explainer:
    """
    Orchestrates SHAP + Mistral for every real login.

    Step 1: SHAP TreeExplainer  → which features mattered most
    Step 2: Mistral AI (free)   → plain English explanation

    Both steps have graceful fallbacks.
    """

    def __init__(self, api_key: str = None):
        self.shap_explainer = SHAPExplainer()
        self.llm_explainer  = LLMExplainer(
            api_key=api_key or os.getenv("MISTRAL_API_KEY", "")
        )
        self._ready = False

    def setup(self, xgb_model) -> None:
        """
        Load XGBoost model into SHAP. Call once at FastAPI startup.

        In main.py:
            from engines.explainer import Explainer
            explainer = Explainer()
            explainer.setup(xgb_model=xgb_model)
        """
        self.shap_explainer.load_model(xgb_model)
        self._ready = True
        print("[Explainer] Phase 8 SHAP + Mistral explainer ready")

    # ──────────────────────────────────────────────────────────────
    # MAIN METHOD
    # ──────────────────────────────────────────────────────────────

    async def explain(
        self,
        feature_vector: np.ndarray,
        feature_names:  list[str],
        risk_result,                    # RiskResult from Phase 7
        context:        dict,
    ) -> ExplainResult:
        """
        Run SHAP + Mistral explanation for one real login.

        Args:
            feature_vector: Scaled 15-element numpy array
            feature_names:  Feature names from model_meta.json
            risk_result:    Phase 7 RiskResult object
            context:        {hour, usual_hour, dna_match, drift_type,
                             distance_km, speed_kmh}

        Returns:
            ExplainResult — add to API response as explanation.to_dict()
        """
        # ── 1. SHAP computation ────────────────────────────────
        shap_result = self.shap_explainer.explain(
            feature_vector   = feature_vector,
            feature_names    = feature_names,
            risk_score       = risk_result.final_score,
            decision         = risk_result.decision,
            xgb_probability  = risk_result.xgb_prob,
            top_n            = 5,
        )

        # ── 2. Build full context for LLM ─────────────────────
        llm_context = {
            "user_id":    risk_result.user_id,
            "country":    risk_result.country,
            "city":       risk_result.city,
            "dna_match":  risk_result.dna_match,
            "drift_type": risk_result.drift_type,
            **context,
        }

        # ── 3. Mistral LLM explanation ─────────────────────────
        llm_result = await self.llm_explainer.explain(
            shap_result    = shap_result,
            decision       = risk_result.decision,
            risk_score     = risk_result.final_score,
            signals_fired  = risk_result.signals_fired,
            context        = llm_context,
        )

        # ── 4. Combine ─────────────────────────────────────────
        return ExplainResult(
            short_text   = llm_result.short_text,
            full_text    = llm_result.full_text,
            key_reasons  = llm_result.key_reasons,
            shap_factors = shap_result.top_factors,
            risk_factors = shap_result.risk_factors,
            safe_factors = shap_result.safe_factors,
            base_score   = shap_result.base_score,
            used_llm     = llm_result.used_llm,
            model_used   = llm_result.model_used,
            tokens_used  = llm_result.tokens_used,
            is_fallback  = shap_result.is_fallback,
        )

    def explain_sync(
        self,
        feature_vector: np.ndarray,
        feature_names:  list[str],
        risk_result,
        context:        dict,
    ) -> ExplainResult:
        """Synchronous wrapper."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.explain(feature_vector, feature_names,
                                     risk_result, context),
                    )
                    return future.result(timeout=12)
            else:
                return loop.run_until_complete(
                    self.explain(feature_vector, feature_names,
                                 risk_result, context)
                )
        except Exception as e:
            print(f"[Explainer] explain_sync failed: {e}")
            return self._empty_result(risk_result)

    def _empty_result(self, risk_result) -> ExplainResult:
        return ExplainResult(
            short_text   = f"Risk score: {risk_result.final_score:.0f}/100 — {risk_result.decision}",
            full_text    = f"Decision: {risk_result.decision}",
            key_reasons  = risk_result.signals_fired[:3] if risk_result.signals_fired else [],
            shap_factors = [],
            risk_factors = [],
            safe_factors = [],
            base_score   = 0.0,
            used_llm     = False,
            model_used   = "none",
            tokens_used  = 0,
            is_fallback  = True,
        )


# ── Singleton ──────────────────────────────────────────────────────
_instance: Optional[Explainer] = None

def get_explainer(api_key: str = None) -> Explainer:
    """Return singleton Explainer. Call get_explainer() in Phase 10 main.py."""
    global _instance
    if _instance is None:
        _instance = Explainer(api_key=api_key)
    return _instance
