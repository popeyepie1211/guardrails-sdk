import numpy as np
import pandas as pd
import time
from datetime import timedelta

from guardrail_ai.wdag.graph import WDAG, Node
from guardrail_ai.wdag.executor import WDAGExecutor
from guardrail_ai.core.vitals_engine import VitalsEngine
from guardrail_ai.core.baseline_initializer import BaselineInitializer

print("\n🚀 SIMPLE WDAG TESTING\n")

# ============================================================
# 🔥 MINIMAL FAKE DATA (NO DATASET NEEDED)
# ============================================================
dummy_df = pd.DataFrame({
    "f1": np.random.rand(50),
    "f2": np.random.rand(50),
    "prediction": np.random.rand(50)
})

metadata = {
    "feature_columns": ["f1", "f2"],
    "numerical_features": ["f1", "f2"],
    "categorical_features": [],
    "prediction_column": "prediction",
    "protected_attributes": None,
    "prediction_type": "probability",
    "quasi_identifier_columns": ["f1"],
    "domain": "standard",
    "shap_values": None
}

baseline = BaselineInitializer(dummy_df, metadata).compute()

# ============================================================
# WDAG SETUP
# ============================================================
graph = WDAG()
graph.add_node(Node("Data", "Data Engineer"))
graph.add_node(Node("Model", "ML Engineer"))

graph.add_edge("Data", "Model")

engine = VitalsEngine(baseline, metadata)
executor = WDAGExecutor(graph, engine)

scenarios = []

# ============================================================
# 1️⃣ NORMAL
# ============================================================
metadata["shap_values"] = np.zeros(50)
result = executor.run("Data", dummy_df)

scenarios.append(["Normal", result["status"]])

# ============================================================
# 2️⃣ SINGLE ANOMALY
# ============================================================
metadata["shap_values"] = np.ones(50) * 2.0
result = executor.run("Data", dummy_df)

scenarios.append(["Single Anomaly", result["status"]])

# ============================================================
# 3️⃣ PERSISTENCE
# ============================================================
for _ in range(3):
    metadata["shap_values"] = np.ones(50) * 2.0
    result = executor.run("Data", dummy_df)

scenarios.append(["Persistence", result["status"]])

# ============================================================
# 4️⃣ RECOVERY
# ============================================================
engine.persistence.reset()

metadata["shap_values"] = np.zeros(50)
result = executor.run("Data", dummy_df)

scenarios.append(["Recovery", result["status"]])

# ============================================================
# 5️⃣ HEARTBEAT
# ============================================================
executor.heartbeat.timeout = timedelta(seconds=1)

time.sleep(2)

dead_nodes = executor.heartbeat.check_timeouts()

scenarios.append(["Heartbeat", dead_nodes])

# ============================================================
# 6️⃣ ZOMBIE
# ============================================================
graph.add_node(Node("Zombie", "Test"))

time.sleep(2)

dead_nodes = executor.heartbeat.check_timeouts()

scenarios.append(["Zombie", dead_nodes])

# ============================================================
# 7️⃣ PROPAGATION (BLAST RADIUS 🔥)
# ============================================================
metadata["shap_values"] = np.ones(50) * 3.0
result = executor.run("Data", dummy_df)

model_status = graph.to_dict()["Model"]["status"]

scenarios.append(["Propagation", model_status])

# ============================================================
# PRINT RESULTS
# ============================================================
print("\n========== WDAG SIMPLE TEST ==========\n")

for s in scenarios:
    print(f"{s[0]:<15} → {s[1]}")

print("\n=====================================")

print("\n🚀 DOMAIN-AWARE TESTING\n")

domains = ["healthcare", "finance", "standard"]

for domain in domains:
    print(f"\n--- Testing Domain: {domain} ---")

    # ✅ update domain
    metadata["domain"] = domain

    # 🔥 IMPORTANT: recreate engine + executor
    engine = VitalsEngine(baseline, metadata)
    executor = WDAGExecutor(graph, engine)

    # reset persistence
    engine.persistence.reset()

    # same anomaly
    metadata["shap_values"] = np.ones(50) * 2.0

    result = executor.run("Data", dummy_df)

    print(f"Status → {result['status']}")