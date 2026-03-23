# backend/engines/ml_engine.py
import joblib
import numpy as np
from typing import Dict
from config.settings import settings
import os

# EXACT feature order from your training notebook
FEATURES = [
    "hour_sin", "hour_cos", "hour_deviation", "is_weekend", "is_offhours",
    "new_device", "country_change", "impossible_travel",
    "failed_norm", "resource_sensitivity", "privilege_gap", "login_velocity",
    "multi_attack_flag", "hour_x_newdev", "fail_x_newdev",
]


class MLEngine:
    """Singleton — loads models once at startup, runs inference per request."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def load_models(self):
        if self._loaded:
            return

        model_dir = settings.MODEL_DIR

        # Scaler
        scaler_path = os.path.join(model_dir, "scaler.pkl")
        if os.path.exists(scaler_path):
            self.scaler = joblib.load(scaler_path)
            print(f"✅ Scaler loaded (expects {self.scaler.n_features_in_} features)")
        else:
            self.scaler = None
            print("⚠️ Scaler not found")

        # Isolation Forest
        iso_path = os.path.join(model_dir, "iso_forest.pkl")
        if os.path.exists(iso_path):
            self.iso_forest = joblib.load(iso_path)
            print("✅ Isolation Forest loaded")
        else:
            self.iso_forest = None
            print("⚠️ Isolation Forest not found")

        # XGBoost
        xgb_path = os.path.join(model_dir, "xgb_model.pkl")
        if os.path.exists(xgb_path):
            self.xgb_model = joblib.load(xgb_path)
            print("✅ XGBoost model loaded")
        else:
            self.xgb_model = None
            print("⚠️ XGBoost model not found")

        # Random Forest
        rf_path = os.path.join(model_dir, "rf_model.pkl")
        if os.path.exists(rf_path):
            self.rf_model = joblib.load(rf_path)
            print("✅ Random Forest loaded")
        else:
            self.rf_model = None
            print("⚠️ Random Forest not found")

        self._loaded = True
        print(f"✅ Models loaded. Using {len(FEATURES)} features: {FEATURES}")

    def predict(self, features: Dict) -> Dict[str, float]:
        """
        Run all models. `features` keys must match FEATURES list.
        Returns individual scores on 0-100 scale.
        """
        self.load_models()

        # Build array in EXACT order
        feature_array = np.array(
            [[features.get(f, 0.0) for f in FEATURES]]
        )

        # Scale
        if self.scaler:
            feature_array_scaled = self.scaler.transform(feature_array)
        else:
            feature_array_scaled = feature_array

        scores: Dict[str, float] = {}

        # Isolation Forest
        if self.iso_forest:
            raw = -self.iso_forest.score_samples(feature_array_scaled)[0]
            scores["isolation_forest"] = float(np.clip((raw + 0.5) * 100, 0, 100))

        # XGBoost
        if self.xgb_model:
            prob = self.xgb_model.predict_proba(feature_array_scaled)[0][1]
            scores["xgboost"] = float(prob * 100)

        # Random Forest
        if self.rf_model:
            prob = self.rf_model.predict_proba(feature_array_scaled)[0][1]
            scores["random_forest"] = float(prob * 100)

        return scores


ml_engine = MLEngine()