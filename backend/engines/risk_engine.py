# backend/engines/risk_engine.py
"""
Risk Score Engine — combines ML scores, DNA match, and graph context.
Produces final risk score 0-100 and decision.
"""
from typing import Dict, List, Tuple
from config.settings import settings
from models.schemas import Decision, RiskFactor


class RiskEngine:
    """
    Weighted combination of all intelligence signals.
    Risk = w1*IF + w2*XGB + w3*RF + (100 - DNA_match)*w4 + Graph*w5
    """

    # Ensemble weights
    WEIGHTS = {
        "isolation_forest": 0.15,
        "xgboost": 0.35,
        "random_forest": 0.30,
        "dna_inverse": 0.15,     # 100 - DNA match score
        "graph_risk": 0.05       # Privilege graph risk
    }

    @staticmethod
    def compute_risk(
        ml_scores: Dict[str, float],
        dna_match: float,
        graph_risk: float = 0.0,
        features: Dict = None,
        metadata: Dict = None
    ) -> Tuple[float, Decision, List[RiskFactor]]:
        """
        Compute final risk score and decision.
        
        Returns: (score, decision, risk_factors)
        """
        weights = RiskEngine.WEIGHTS

        # Calculate weighted score
        weighted_sum = 0.0
        total_weight = 0.0

        if "isolation_forest" in ml_scores:
            weighted_sum += ml_scores["isolation_forest"] * weights["isolation_forest"]
            total_weight += weights["isolation_forest"]

        if "xgboost" in ml_scores:
            weighted_sum += ml_scores["xgboost"] * weights["xgboost"]
            total_weight += weights["xgboost"]

        if "random_forest" in ml_scores:
            weighted_sum += ml_scores["random_forest"] * weights["random_forest"]
            total_weight += weights["random_forest"]

        # DNA inverse — higher DNA mismatch = higher risk
        dna_risk = 100 - dna_match
        weighted_sum += dna_risk * weights["dna_inverse"]
        total_weight += weights["dna_inverse"]

        # Graph risk
        weighted_sum += graph_risk * weights["graph_risk"]
        total_weight += weights["graph_risk"]

        # Normalize
        if total_weight > 0:
            final_score = weighted_sum / total_weight
        else:
            final_score = 50.0

        # Clamp to 0-100
        final_score = max(0, min(100, final_score))

        # === Apply rule-based overrides ===
        if features:
            # Impossible travel → minimum score 70
            if features.get("impossible_travel", 0) == 1:
                final_score = max(final_score, 70.0)

            # Many failed attempts → boost score
            # failed_norm is 0-1 (divided by 10), so 0.5 = 5 attempts
            failed_norm = features.get("failed_norm", 0)
            if failed_norm >= 0.5:       # 5+ attempts
                final_score = max(final_score, 80.0)
            elif failed_norm >= 0.3:     # 3+ attempts
                final_score = max(final_score, 50.0)

            # Multi-attack flag → minimum score 75
            if features.get("multi_attack_flag", 0) == 1:
                final_score = max(final_score, 75.0)

        # === Decision ===
        if final_score <= settings.ALLOW_THRESHOLD:
            decision = Decision.ALLOW
        elif final_score <= settings.OTP_THRESHOLD:
            decision = Decision.OTP
        elif final_score <= settings.STEPUP_THRESHOLD:
            decision = Decision.STEPUP
        else:
            decision = Decision.BLOCK

        # === Build risk factors explanation ===
        risk_factors = RiskEngine._build_risk_factors(
            ml_scores, dna_match, graph_risk, features, metadata
        )

        return round(final_score, 1), decision, risk_factors

    @staticmethod
    def _build_risk_factors(
        ml_scores: Dict,
        dna_match: float,
        graph_risk: float,
        features: Dict,
        metadata: Dict
    ) -> List[RiskFactor]:
        factors = []

        if features:
            if features.get("impossible_travel", 0) == 1:
                factors.append(RiskFactor(
                    factor="impossible_travel",
                    contribution=25.0,
                    description=f"Login from {metadata.get('country', 'unknown')} — impossible travel detected"
                ))

            if features.get("new_device", 0) == 1:
                factors.append(RiskFactor(
                    factor="new_device",
                    contribution=15.0,
                    description="Login from a new/unseen device"
                ))

            if features.get("country_change", 0) == 1:
                factors.append(RiskFactor(
                    factor="country_change",
                    contribution=20.0,
                    description=f"Login from new country: {metadata.get('country', 'unknown')}"
                ))

            failed_norm = features.get("failed_norm", 0)
            if failed_norm > 0:
                failed_count = int(failed_norm * 10)  # convert back to count
                factors.append(RiskFactor(
                    factor="failed_attempts",
                    contribution=min(failed_count * 8.0, 30.0),
                    description=f"{failed_count} failed login attempt(s) before this login"
                ))

            hour_dev = features.get("hour_deviation", 0)
            if hour_dev > 0.3:
                factors.append(RiskFactor(
                    factor="unusual_hour",
                    contribution=hour_dev * 12.0,
                    description=f"Login at unusual hour ({metadata.get('hour', '?')}:00)"
                ))

            if features.get("is_offhours", 0) == 1:
                factors.append(RiskFactor(
                    factor="off_hours",
                    contribution=8.0,
                    description="Login during off-hours (before 6 AM or after 10 PM)"
                ))

            resource_sens = features.get("resource_sensitivity", 0)
            if resource_sens > 0.5:
                factors.append(RiskFactor(
                    factor="sensitive_resource",
                    contribution=resource_sens * 10.0,
                    description=f"Accessing sensitive resource: {metadata.get('resource', 'unknown')}"
                ))

            if features.get("multi_attack_flag", 0) == 1:
                factors.append(RiskFactor(
                    factor="multi_attack",
                    contribution=20.0,
                    description="Multiple attack signals detected simultaneously"
                ))

        # DNA match factor
        if dna_match >= 80:
            factors.append(RiskFactor(
                factor="known_behavior",
                contribution=-10.0,
                description=f"Behavior matches DNA profile ({dna_match:.0f}% match)"
            ))
        elif dna_match < 50 and dna_match > 0:
            factors.append(RiskFactor(
                factor="behavior_mismatch",
                contribution=15.0,
                description=f"Behavior deviates from DNA profile ({dna_match:.0f}% match)"
            ))

        factors.sort(key=lambda x: x.contribution, reverse=True)
        return factors