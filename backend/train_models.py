import json, os, joblib
import numpy as np
import shap
from datetime import datetime, timezone
from collections import Counter
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from xgboost import XGBClassifier
import sklearn
import xgboost as xgb
from features import engineer_features, FEATURE_NAMES

def build_feature_matrix(sessions):
    X_rows   = []
    y_labels = []
    user_histories = {}
    
    for session in sessions:
        uid = session["user_id"]
        history = user_histories.get(uid, [])
        feats = engineer_features(session, history)
        X_rows.append(list(feats.values()))
        y_labels.append(session["risk_label"])
        user_histories.setdefault(uid, []).append(session)
    
    return np.array(X_rows, dtype=np.float32), np.array(y_labels, dtype=np.int32)

def main():
    print(f"[{datetime.now():%H:%M:%S}] Loading session data...")
    data_path = os.path.join(os.path.dirname(__file__), "data", "sessions.json")
    with open(data_path) as f:
        sessions = json.load(f)
    print(f"  Loaded {len(sessions)} sessions")
    
    X, y = build_feature_matrix(sessions)
    print(f"  Feature matrix shape: {X.shape}")
    print(f"  Label distribution: {dict(Counter(y))}")
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"  Train: {len(X_train)}, Test: {len(X_test)}")
    
    print(f"[{datetime.now():%H:%M:%S}] Fitting StandardScaler...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled  = scaler.transform(X_test)
    
    print(f"[{datetime.now():%H:%M:%S}] Training Isolation Forest...")
    n_anomalies = sum(1 for s in sessions if s.get("is_anomaly", False))
    contamination = n_anomalies / len(sessions)
    iso_forest = IsolationForest(n_estimators=150, contamination=contamination, random_state=42, n_jobs=-1)
    iso_forest.fit(X_train_scaled)
    
    iso_scores = iso_forest.decision_function(X_train_scaled)
    iso_ref_min = float(iso_scores.min())
    iso_ref_max = float(iso_scores.max())
    
    label_counts = Counter(y_train)
    n_majority = label_counts[0]
    n_minority = label_counts[2]
    spw = min(n_majority / n_minority, 30) if n_minority > 0 else 1.0
    
    print(f"[{datetime.now():%H:%M:%S}] Training XGBoost with scale_pos_weight={spw:.1f}...")
    xgb_model = XGBClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.05,
        scale_pos_weight=spw, eval_metric="logloss", random_state=42
    )
    xgb_model.fit(X_train_scaled, y_train)
    
    y_pred = xgb_model.predict(X_test_scaled)
    acc = accuracy_score(y_test, y_pred)
    print(f"  XGBoost Accuracy: {acc:.4f}\n")
    print(classification_report(y_test, y_pred))
    assert acc > 0.85, f"Accuracy too low: {acc}"
    
    explainer = shap.TreeExplainer(xgb_model)
    shap_vals = explainer.shap_values(X_test_scaled[:5])
    assert shap_vals is not None, "SHAP verification failed"
    
    os.makedirs(os.path.join(os.path.dirname(__file__), "data", "models"), exist_ok=True)
    model_dir = os.path.join(os.path.dirname(__file__), "data", "models")
    joblib.dump(scaler, os.path.join(model_dir, "scaler.pkl"))
    joblib.dump(iso_forest, os.path.join(model_dir, "isolation_forest.pkl"))
    joblib.dump(xgb_model, os.path.join(model_dir, "xgboost.pkl"))
    
    meta = {
       "sklearn_version": sklearn.__version__,
       "xgb_version": xgb.__version__,
       "w_xgb": 0.60, "w_iso": 0.40,
       "iso_ref_min": iso_ref_min, "iso_ref_max": iso_ref_max,
       "feature_names": FEATURE_NAMES,
       "trained_at": datetime.now(timezone.utc).isoformat()
    }
    with open(os.path.join(model_dir, "model_meta.json"), "w") as f:
        json.dump(meta, f)
    
    print("\nModels & metadata successfully saved.")

if __name__ == "__main__":
    main()
