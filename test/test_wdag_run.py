# pipeline_full_eval.py
# ------------------------------------------------------------
# FULL END-TO-END PIPELINE (WDAG + ENGINE + BATCH + METRICS)
# Produces Table 1 for Research Paper
# ------------------------------------------------------------

import time
import numpy as np
import pandas as pd

from sklearn.datasets import fetch_california_housing
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from datetime import timedelta
# -----------------------------
# Guardrail AI Imports
# -----------------------------
from guardrail_ai.core.batch_manager import BatchManager
from guardrail_ai.core.baseline_initializer import BaselineInitializer
from guardrail_ai.core.vitals_engine import VitalsEngine

from guardrail_ai.wdag.node import Node
from guardrail_ai.wdag.graph import WDAG
from guardrail_ai.wdag.executor import WDAGExecutor


# ============================================================
# 1. Load Dataset
# ============================================================
print("📦 Loading dataset...\n")

data = fetch_california_housing(as_frame=True)
df = data.frame.copy()

feature_columns = list(data.feature_names)
target_col = "MedHouseVal"

X = df[feature_columns]
y = df[target_col]

# ============================================================
# 2. Train/Test Split
# ============================================================
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# ============================================================
# 3. Train Model
# ============================================================
print("🤖 Training model...\n")

model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# ============================================================
# 4. Predictions
# ============================================================
train_preds = model.predict(X_train)
test_preds = model.predict(X_test)

# Normalize → probability-like
train_preds = (train_preds - train_preds.min()) / (train_preds.max() - train_preds.min())
test_preds = (test_preds - test_preds.min()) / (test_preds.max() - test_preds.min())

train_df = X_train.copy()
train_df["prediction"] = train_preds

test_df = X_test.copy()
test_df["prediction"] = test_preds

# ============================================================
# 5. Metadata
# ============================================================
metadata = {
    "feature_columns": feature_columns,
    "numerical_features": feature_columns,
    "categorical_features": [],
    "prediction_column": "prediction",
    "protected_attributes": None,
    "prediction_type": "probability",
    "quasi_identifier_columns": feature_columns[:2],
    "domain": "standard",
    "shap_values": None
}

# ============================================================
# 6. Baseline
# ============================================================
print("📊 Initializing baseline...\n")

baseline = BaselineInitializer(train_df, metadata).compute()

# ============================================================
# 7. WDAG Setup (FULL PIPELINE)
# ============================================================
graph = WDAG()

graph.add_node(Node("Data", "Data Engineer"))
graph.add_node(Node("Model", "ML Engineer"))
graph.add_node(Node("Deployment", "DevOps"))

graph.add_edge("Data", "Model", weight=0.8)
graph.add_edge("Model", "Deployment", weight=0.9)

engine = VitalsEngine(baseline, metadata)
executor = WDAGExecutor(graph, engine)

batch_manager = BatchManager(batch_size=50)


print("\n🚀 WDAG EDGE CASE TESTING\n")

scenarios = []

# ============================================================
# 1️⃣ NORMAL OPERATION
# ============================================================
batch = test_df.sample(50)

metadata["shap_values"] = np.random.normal(0.05, 0.01, len(batch))
result = executor.run("Data", batch)

scenarios.append([
    "Normal Operation",
    "Healthy input",
    result["status"],
    "System stable"
])

# ============================================================
# 2️⃣ DATA DRIFT
# ============================================================
drift_batch = batch.copy()

for col in metadata["numerical_features"]:
    drift_batch[col] *= np.random.normal(1.5, 0.2, len(drift_batch))

metadata["shap_values"] = np.random.normal(0.05, 0.01, len(drift_batch))
result = executor.run("Data", drift_batch)

scenarios.append([
    "Data Drift",
    "Feature distribution shift",
    result["status"],
    "Drift detected"
])

# ============================================================
# 3️⃣ PERSISTENCE ESCALATION
# ============================================================
for _ in range(3):
    metadata["shap_values"] = np.random.normal(2.0, 0.5, len(batch))
    result = executor.run("Data", batch)

scenarios.append([
    "Persistence Escalation",
    "Repeated anomaly",
    result["status"],
    "Escalation triggered"
])

# ============================================================
# 4️⃣ RECOVERY
# ============================================================
engine.persistence.reset()
metadata["shap_values"] = np.random.normal(0.05, 0.01, len(batch))
result = executor.run("Data", batch)

scenarios.append([
    "Recovery",
    "Normal input restored",
    result["status"],
    "System stabilizes"
])

# ============================================================
# 5️⃣ HEARTBEAT FAILURE
# ============================================================
print("\n⏳ Simulating heartbeat failure...")
executor.heartbeat.timeout = timedelta(seconds=1)
time.sleep(2)  # simulate delay

timed_out_nodes = executor.heartbeat.check_timeouts()

scenarios.append([
    "Heartbeat Failure",
    "No data received",
    str(timed_out_nodes),
    "Node marked inactive"
])

# ============================================================
# 6️⃣ ZOMBIE NODE
# ============================================================
graph.add_node(Node("Zombie", "Test"))
# 🔥 Ensure timeout applies
executor.heartbeat.timeout = timedelta(seconds=1)
time.sleep(2)
timed_out_nodes = executor.heartbeat.check_timeouts()

scenarios.append([
    "Zombie Node",
    "Node never pinged",
    str(timed_out_nodes),
    "Detected as inactive"
])

# ============================================================
# 7️⃣ IMPACT PROPAGATION
# ============================================================
metadata["shap_values"] = np.random.normal(2.0, 0.5, len(batch))
result = executor.run("Data", batch)

model_status = graph.to_dict()["Model"]["status"]

scenarios.append([
    "Impact Propagation",
    "Critical Data node",
    model_status,
    "Downstream affected"
])

# ============================================================
# PRINT TABLE
# ============================================================
print("\n================ TABLE 2: WDAG GOVERNANCE ================\n")

print(f"{'Scenario':<25} {'Trigger':<30} {'Observed':<20} Interpretation")
print("-"*100)

for s in scenarios:
    print(f"{s[0]:<25} {s[1]:<30} {s[2]:<20} {s[3]}")

print("\n==========================================================")