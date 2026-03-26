import os
import json
import logging
import numpy as np
import joblib

logger = logging.getLogger(__name__)
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "models")

class MLEngine:
    def __init__(self):
        self.isolation_forest = self.xgboost_model = self.scaler = None
        self.meta = {}
        self._loaded = False
        self._shap_explainer = None

    def load_models(self):
        try:
            self.scaler = joblib.load(os.path.join(MODEL_DIR, "scaler.pkl"))
            self.isolation_forest = joblib.load(os.path.join(MODEL_DIR, "isolation_forest.pkl"))
            self.xgboost_model = joblib.load(os.path.join(MODEL_DIR, "xgboost.pkl"))
            mp = os.path.join(MODEL_DIR, "model_meta.json")
            if os.path.exists(mp):
                with open(mp) as f:
                    self.meta = json.load(f)
            import shap
            self._shap_explainer = shap.TreeExplainer(self.xgboost_model)
            self._loaded = True
            logger.info("✅ ML models loaded (version=%s)", self.meta.get("version", "?"))
        except Exception as e:
            logger.error(f"❌ Model loading error: {e}")
            self._loaded = False

    @property
    def is_loaded(self):
        return self._loaded

    def score(self, features):
        if not self._loaded:
            return {"iso_score": 0.5, "xgb_score": 0.5, "shap_values": [0.0]*len(features)}
        try:
            X = self.scaler.transform(features.reshape(1, -1))
            raw_if = self.isolation_forest.decision_function(X)[0]
            
            if "iso_ref_min" in self.meta and "iso_ref_max" in self.meta:
                mi = self.meta["iso_ref_min"]
                ma = self.meta["iso_ref_max"]
                iso_score = float(np.clip((ma - raw_if) / (ma - mi + 1e-9), 0, 1))
            else:
                iso_score = float(np.clip((0.5 - raw_if) / 0.5, 0, 1))
            
            xgb_score = float(self.xgboost_model.predict_proba(X)[0][1])
            
            sv = self._shap_explainer.shap_values(X)
            if isinstance(sv, list):
                sv = sv[1]
            if len(sv.shape) == 3:
                sv = sv[:, :, 1]
            if len(sv.shape) > 1:
                shap_list = [float(v) for v in sv[0]]
            else:
                shap_list = [float(v) for v in sv]
            
            return {
                "iso_score": iso_score,
                "xgb_score": xgb_score,
                "shap_values": shap_list
            }
        except Exception as e:
            logger.error(f"Error scoring features: {e}")
            return {"iso_score": 0.5, "xgb_score": 0.5, "shap_values": [0.0]*len(features)}