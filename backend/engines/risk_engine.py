W_XGB, W_ISO, W_GRAPH = 0.60, 0.40, 0.20

class RiskEngine:
    def evaluate(self, ml_scores, dna_match, graph_score, flags, failed_attempts, feature_dict, login_count=0, days_active=0, role="viewer", hitl_trusted=False):
        xgb_score = ml_scores.get("xgb_score", 0.5)
        iso_score = ml_scores.get("iso_score", 0.5)
        
        confidence = min(1.0, (login_count / 50.0) * 0.5 + (max(days_active, 1) / 90.0) * 0.5)
        dna_weight = 0.10 + (confidence * 0.30)
        
        base = (W_ISO * iso_score) + (W_XGB * xgb_score)
        
        normalized_dna = dna_match / 100.0
        graph_risk = graph_score / 25.0
        
        risk_score = (base * (1.0 - dna_weight)) + ((1.0 - normalized_dna) * dna_weight) + (W_GRAPH * graph_risk)
        raw = risk_score * 100.0
        
        overrides = []
        if flags.get("impossible_travel"):
            raw = max(raw, 70); overrides.append("impossible_travel→70")
        fn = min(feature_dict.get("failed_attempts", 0) / 10.0, 1.0)
        if fn >= 0.5:
            raw = max(raw, 80); overrides.append("5+failed→80")
        elif fn >= 0.3:
            raw = max(raw, 50); overrides.append("3+failed→50")
        if flags.get("multi_attack_flag"):
            raw = max(raw, 75); overrides.append("multi_attack→75")

        # HITL Trust Override
        if hitl_trusted:
            raw = min(raw, 15)
            overrides.append("HITL_Approved_Trust→15")
            
        # Admin Strictness: Zero Trust for anomalies
        if role == "admin":
            admin_anomalies = []
            if flags.get("new_device"): admin_anomalies.append("new_device")
            if flags.get("country_change"): admin_anomalies.append("new_country")
            if flags.get("unusual_resource"): admin_anomalies.append("unusual_resource")
            if flags.get("is_offhours"): admin_anomalies.append("offhours")
            
            if len(admin_anomalies) == 1:
                # Single anomaly for admin (like new device) shouldn't block, just MFA
                raw = max(raw, 65)
                overrides.append(f"Admin_Soft_Override({admin_anomalies[0]})→65")
            elif len(admin_anomalies) > 1:
                # Multiple anomalies for admin is a high-risk block
                raw = max(raw, 85)
                overrides.append(f"Admin_Strict_Block({','.join(admin_anomalies)})→85")
            
        score = round(min(max(raw, 0), 100), 1)
        if score < 30: dec = "ALLOW"
        elif score < 60: dec = "OTP"
        elif score < 80: dec = "STEPUP"
        else: dec = "BLOCK"
        
        factors = []
        if xgb_score > 0.3: factors.append({"factor": "ml_xgboost", "contribution": round(xgb_score*W_XGB*100,1), "description": f"XGBoost: {round(xgb_score*100,1)}%"})
        if iso_score > 0.3: factors.append({"factor": "ml_iso", "contribution": round(iso_score*W_ISO*100,1), "description": f"IF: {round(iso_score*100,1)}%"})
        dr = 100 - dna_match
        if dr > 20: factors.append({"factor": "dna_mismatch", "contribution": round(dr*dna_weight,1), "description": f"DNA match: {dna_match}%"})
        elif dna_match > 80: factors.append({"factor": "known_behavior", "contribution": round(-dna_match*dna_weight,1), "description": f"DNA: {dna_match}%"})
        if graph_score > 0: factors.append({"factor": "privilege", "contribution": round(graph_score*W_GRAPH*4,1), "description": f"Graph: {graph_score}"})
        if flags.get("new_device"): factors.append({"factor": "new_device", "contribution": 15.0, "description": "New device"})
        if flags.get("country_change"): factors.append({"factor": "new_country", "contribution": 20.0, "description": "New country"})
        if flags.get("impossible_travel"): factors.append({"factor": "impossible_travel", "contribution": 25.0, "description": "Impossible travel"})
        if flags.get("is_offhours"): factors.append({"factor": "off_hours", "contribution": 5.0, "description": "Off-hours"})
        if flags.get("multi_attack_flag"): factors.append({"factor": "multi_attack", "contribution": 15.0, "description": "3+ signals"})
        for o in overrides: factors.append({"factor": "override", "contribution": 0, "description": o})
        factors.sort(key=lambda x: abs(x["contribution"]), reverse=True)
        return {"score": score, "decision": dec, "risk_factors": factors}