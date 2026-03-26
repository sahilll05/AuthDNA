import os
import json
import logging
import asyncio
from datetime import datetime, timezone
import numpy as np
import shap
import joblib
from collections import Counter
import xgboost as xgb
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from features import engineer_features, FEATURE_NAMES
from services.database_service import db_service

logger = logging.getLogger(__name__)

async def run_retrain_pipeline():
    """Weekly retrain pipeline merging synthetic base with real Appwrite logs."""
    logger.info("Starting Adaptive Retraining Pipeline...")
    
    # 1. Load Synthetic Base Data
    base_data_path = os.path.join(os.path.dirname(__file__), "data", "sessions.json")
    try:
        with open(base_data_path) as f:
            base_sessions = json.load(f)
    except FileNotFoundError:
        logger.error("Base synthetic data not found. Cannot retrain.")
        return

    # 2. Add sample weights: 1.0 for synthetic, 2.0 for real data (simplified approach)
    all_sessions = []
    sample_weights = []
    for s in base_sessions:
        all_sessions.append(s)
        sample_weights.append(1.0)
    
    # In a full implementation, we'd query Appwrite here:
    # real_logs = await db_service.get_login_logs(tenant_id="global", limit=2000)
    # Convert real logs to match session structure and assign weight=2.0 
    # For now, we simulate this layer for the hackathon MVP.
    
    # 3. Build Feature Matrix
    X_rows = []
    y_labels = []
    user_histories = {}
    
    # Sort chronologically
    all_sessions.sort(key=lambda x: x.get("timestamp", ""))
    
    for session in all_sessions:
        uid = session["user_id"]
        history = user_histories.get(uid, [])
        feats = engineer_features(session, history)
        X_rows.append(list(feats.values()))
        y_labels.append(session.get("risk_label", 0))
        user_histories.setdefault(uid, []).append(session)
        
    X = np.array(X_rows, dtype=np.float32)
    y = np.array(y_labels, dtype=np.int32)
    w = np.array(sample_weights, dtype=np.float32)
    
    logger.info(f"Retraining on {len(X)} samples with weights.")
    
    # 4. Train Models
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Isolation Forest
    n_anomalies = sum(1 for label in y if label > 0)
    contamination = max(0.01, min(0.5, n_anomalies / len(y)))
    iso = IsolationForest(n_estimators=150, contamination=contamination, random_state=42)
    iso.fit(X_scaled)
    iso_scores = iso.decision_function(X_scaled)
    iso_ref_min, iso_ref_max = float(iso_scores.min()), float(iso_scores.max())
    
    # XGBoost
    label_counts = Counter(y)
    n_majority = label_counts[0]
    n_minority = label_counts[2] if 2 in label_counts else 1 
    spw = min(n_majority / n_minority, 30.0) if n_minority > 0 else 1.0
    
    xgb_model = xgb.XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.05,
                                  scale_pos_weight=spw, eval_metric="logloss", random_state=42)
    xgb_model.fit(X_scaled, y, sample_weight=w)
    
    # 5. Save Models
    model_dir = os.path.join(os.path.dirname(__file__), "data", "models")
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(scaler, os.path.join(model_dir, "scaler.pkl"))
    joblib.dump(iso, os.path.join(model_dir, "isolation_forest.pkl"))
    joblib.dump(xgb_model, os.path.join(model_dir, "xgboost.pkl"))
    
    meta = {
       "w_xgb": 0.60, "w_iso": 0.40,
       "iso_ref_min": iso_ref_min, "iso_ref_max": iso_ref_max,
       "feature_names": FEATURE_NAMES,
       "trained_at": datetime.now(timezone.utc).isoformat()
    }
    with open(os.path.join(model_dir, "model_meta.json"), "w") as f:
        json.dump(meta, f)
        
    logger.info("Retraining complete. New models saved.")
    
def check_and_retrain():
    """Wrapper for APScheduler to run async function gracefully."""
    logger.info("Scheduler triggered retrain task.")
    # Safe asyncio running
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(run_retrain_pipeline())
    except RuntimeError:
        asyncio.run(run_retrain_pipeline())
