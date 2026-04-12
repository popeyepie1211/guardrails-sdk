import pandas as pd
import numpy as np

from guardrail_ai.wdag.node import Node
from guardrail_ai.wdag.graph import WDAG
from guardrail_ai.wdag.executor import WDAGExecutor
from guardrail_ai.core.vitals_engine import VitalsEngine
from guardrail_ai.core.batch_manager import BatchManager
from guardrail_ai.core.baseline_initializer import BaselineInitializer
from guardrail_ai.config import (
    DEFAULT_BATCH_SIZE,
    MIN_BATCH_SIZE,
    BATCH_TIMEOUT_SECONDS
)


from sklearn.datasets import fetch_california_housing
import pandas as pd
import numpy as np

# -----------------------------
# Load real dataset
# -----------------------------
data = fetch_california_housing()

full_df = pd.DataFrame(data.data, columns=data.feature_names)
full_df["target"] = data.target

# -----------------------------
# Create prediction (simulate model)
# -----------------------------
full_df["prediction"] = full_df["target"] / full_df["target"].max()
# -----------------------------
# 3️⃣ Baseline (from training data)
# -----------------------------
metadata = {
    "feature_columns": list(data.feature_names),
    "numerical_features": list(data.feature_names),
    "categorical_features": [],
    "prediction_column": "prediction",
    "protected_attributes": None,
    "prediction_type": "probability",
    "quasi_identifier_columns": list(data.feature_names[:2]),
    "domain": "standard",
    "shap_values": np.random.randn(len(full_df)),
}

initializer = BaselineInitializer(full_df, metadata)
baseline = initializer.compute()

# -----------------------------
# 4️⃣ WDAG Setup
# -----------------------------
graph = WDAG()

graph.add_node(Node("Data", "Data Engineer"))
graph.add_node(Node("Model", "ML Engineer"))
graph.add_node(Node("Deployment", "DevOps"))

graph.add_edge("Data", "Model", weight=0.8)
graph.add_edge("Model", "Deployment", weight=0.9)

engine = VitalsEngine(baseline, metadata)
executor = WDAGExecutor(graph, engine)

# -----------------------------
# 5️⃣ Batch Manager
# -----------------------------
batch_manager = BatchManager(
    batch_size=DEFAULT_BATCH_SIZE,
    min_batch_size=MIN_BATCH_SIZE,
    timeout_seconds=5
)

# -----------------------------
# 6️⃣ Simulate streaming
# -----------------------------
# -----------------------------
# 6️⃣ Simulate streaming
# -----------------------------
print("\n===== STREAMING START =====")

for i in range(0, len(full_df), 10):
    chunk = full_df.iloc[i:i+10]

    batch = batch_manager.add(chunk)

    if batch is not None:
        print(f"\n🚀 Batch Ready (size={len(batch)})")

        result = executor.run("Data", batch)

        print("Status:", result["status"])

        # ✅ SAFE HANDLING
        if "metrics" in result:
            print("---- Metric Status ----")
            for k, v in result["metrics"].items():
                print(f"{k}: {v['status']}")

            print("\n---- Persistence History ----")
            for metric in result["metrics"]:
                history = engine.persistence.get_history(metric)
                print(f"{metric}: {history}")

        else:
            print("⚠ System Failure Detected")
            print(result["error"])
            print("\nDEBUG ERROR:", result["error"])

# -----------------------------
# 7️⃣ Flush remaining
# -----------------------------
final_batch = batch_manager.flush()

if final_batch is not None:
    print(f"\n🚀 Final Batch (size={len(final_batch)})")

    result = executor.run("Data", final_batch)

    print("Final Status:", result["status"])
    
print("\n===== FINAL GRAPH =====")
print(graph.to_dict())