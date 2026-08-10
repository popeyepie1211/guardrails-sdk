"""
End-to-end integration test: send a real batch through process_batch()
using a combined sklearn Pipeline at model_artifact_path.
Proves SHAP works through the full ingestion → worker pipeline.
"""
import sys, os, json, uuid
import numpy as np
import pandas as pd
import joblib
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stdout
)

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split
from datetime import datetime, timezone
import psycopg
from psycopg.rows import dict_row
import redis

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from worker_auditor import process_batch, get_db_connection, model_bundle_cache

print("\n" + "="*70)
print("  E2E PIPELINE INTEGRATION TEST")
print("="*70 + "\n")

# Build artifacts
data = load_breast_cancer()
feature_names = list(data.feature_names[:5])
X = pd.DataFrame(data.data[:, :5], columns=feature_names)
y = data.target
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("clf", RandomForestClassifier(n_estimators=50, random_state=42))
])
pipeline.fit(X_train, y_train)

artifact_dir = os.path.join(os.path.dirname(__file__), "_e2e_artifacts")
os.makedirs(artifact_dir, exist_ok=True)
pipeline_path = os.path.join(artifact_dir, "pipeline.pkl")
bg_path = os.path.join(artifact_dir, "bg.csv")
joblib.dump(pipeline, pipeline_path)
X_train.head(100).to_csv(bg_path, index=False)

# Setup DB
db_conn = get_db_connection()
redis_client = redis.from_url("redis://localhost:6379")
redis_client.ping()

model_id = f"e2e-pipeline-{uuid.uuid4().hex[:8]}"

# Create baseline with pipeline model_artifact_path
baseline = {
    "baseline_summary": {
        "gini": {"mean": 0.5, "std": 0.1},
        "psi": {"mean": 0.1, "std": 0.05},
        "linf": {"mean": 0.2, "std": 0.1},
        "ood_score": {"mean": 0.1, "std": 0.05},
        "privacy_score": {"mean": 0.7, "std": 0.1},
        "shap_importance": {"mean": 0.5, "std": 0.2},
    },
    "distributions": {"numerical": {f: X_train[f].tolist()[:50] for f in feature_names}}
}
metadata = {
    "feature_columns": feature_names,
    "feature_order": feature_names,
    "numerical_features": feature_names,
    "categorical_features": [],
    "prediction_column": "prediction",
    "prediction_type": "probability",
    "quasi_identifier_columns": [feature_names[0]],
    "domain": "standard",
    "model_name": "E2E Pipeline Test",
    "model_version": "v1",
    "model_artifact_path": pipeline_path,
    # NO preprocessor_artifact_path — testing auto-split
    "shap_background_path": bg_path,
    "shap_explainer_type": "tree",
    "shap_background_rows": 100,
}

with db_conn.cursor() as cur:
    cur.execute(
        """INSERT INTO model_baselines (model_id, baseline, metadata, version)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (model_id) DO UPDATE SET baseline=EXCLUDED.baseline,
           metadata=EXCLUDED.metadata, version=EXCLUDED.version, updated_at=NOW();""",
        (model_id, json.dumps(baseline), json.dumps(metadata), "v1"),
    )
db_conn.commit()
print(f"[SETUP] Created baseline for {model_id}")

# Build batch payload
preds = pipeline.predict_proba(X_test.head(30)[feature_names])[:, 1]
payload = []
for i in range(30):
    row = X_test.iloc[i]
    payload.append({
        "eventId": f"evt-{uuid.uuid4().hex[:8]}",
        "modelId": model_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latencyMs": 10.0 + i * 0.1,
        "inputFeatures": {f: float(row[f]) for f in feature_names},
        "prediction": {"value": float(preds[i]), "type": "probability"},
        "metadata": {}
    })

batch = {
    "batchId": f"e2e-batch-{uuid.uuid4().hex[:8]}",
    "modelId": model_id,
    "payload": payload,
    "metadata": {}
}

model_bundle_cache.clear()

print(f"\n[INFO] Sending batch through process_batch()...\n")
success = process_batch(batch, redis_client, db_conn)
print(f"\n[RESULT] process_batch returned: {success}")

if success:
    # Query the persisted results
    with db_conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT metrics FROM model_vitals WHERE model_id = %s ORDER BY time DESC LIMIT 1;",
            (model_id,)
        )
        row = cur.fetchone()
    
    if row:
        metrics = row['metrics'] if isinstance(row['metrics'], dict) else json.loads(row['metrics'])
        shap_status = metrics.get('shap_status', {})
        fi = metrics.get('shap_feature_importance', {})
        tf = metrics.get('shap_top_features', [])
        print(f"\n[DB] shap_status: {shap_status}")
        print(f"[DB] shap_feature_importance: {fi}")
        print(f"[DB] shap_top_features: {tf}")
        
        if shap_status.get('available'):
            print("\n[PASS] E2E: SHAP computed successfully via combined Pipeline through full worker pipeline!")
        else:
            print(f"\n[FAIL] E2E: SHAP not available: {shap_status.get('reason')}")
    else:
        print("[FAIL] No model_vitals row found")
else:
    print("[FAIL] process_batch failed")

# Cleanup
print("\n[CLEANUP]")
with db_conn.cursor() as cur:
    for table in ["node_status_history", "heartbeat_log", "model_vitals",
                   "governance_decisions", "shap_summary", "raw_inference_events"]:
        cur.execute(f"DELETE FROM {table} WHERE model_id = %s;", (model_id,))
    cur.execute("DELETE FROM model_baselines WHERE model_id = %s;", (model_id,))
    cur.execute("DELETE FROM models WHERE model_id = %s;", (model_id,))
db_conn.commit()
db_conn.close()
redis_client.close()

import shutil
shutil.rmtree(artifact_dir, ignore_errors=True)
print("[OK] Cleanup complete\n")
