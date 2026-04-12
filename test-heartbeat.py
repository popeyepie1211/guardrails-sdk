from datetime import timedelta
import time
import pandas as pd
import numpy as np

from guardrail_ai.wdag.node import Node
from guardrail_ai.wdag.graph import WDAG
from guardrail_ai.wdag.executor import WDAGExecutor
from guardrail_ai.wdag.monitor import WDAGMonitor
from guardrail_ai.core.vitals_engine import VitalsEngine


# -----------------------------
# Dummy data
# -----------------------------
df = pd.DataFrame({
    "age": [25, 30, 40],
    "income": [50000, 60000, 70000],
    "gender": ["M", "F", "M"],
    "prediction": [0.8, 0.7, 0.9],
})

metadata = {
    "feature_columns": ["age", "income"],
    "numerical_features": ["age", "income"],
    "categorical_features": ["gender"],
    "prediction_column": "prediction",
    "protected_attributes": {"type": "categorical", "columns": ["gender"]},
    "prediction_type": "probability",
    "quasi_identifier_columns": ["age", "income"],
    "domain": "standard",
    "shap_values": np.random.randn(3),
}

baseline = {
    "baseline_summary": {
        "gini": {"mean": 0.4, "std": 0.1},
        "psi": {"mean": 0.05, "std": 0.02},
        "linf": {"mean": 0.3, "std": 0.1},
        "ood_score": {"mean": 0.1, "std": 0.05},
        "privacy_score": {"mean": 0.6, "std": 0.1},
        "statistical_parity": {"mean": 0.2, "std": 0.1},
        "shap_importance": {"mean": 0.5, "std": 0.2},
    },
    "distributions": {
        "numerical": {
            "age": df["age"].values,
            "income": df["income"].values
        }
    }
}

# -----------------------------
# Setup WDAG
# -----------------------------
graph = WDAG()
graph.add_node(Node("Data", "Data Engineer"))
graph.add_node(Node("Model", "ML Engineer"))

graph.add_edge("Data", "Model")

engine = VitalsEngine(baseline, metadata)
executor = WDAGExecutor(graph, engine)
executor.heartbeat.timeout = timedelta(seconds=3)
monitor = WDAGMonitor(executor, interval_seconds=2)

# -----------------------------
# Simulate activity
# -----------------------------
print("\n--- RUNNING NODE ---")
executor.run("Data", df)

print("\n--- WAIT (simulate no data) ---")
time.sleep(5)

print("\n--- START MONITOR ---")
monitor.start(cycles=3)

print("\n--- FINAL GRAPH ---")
print(graph.to_dict())