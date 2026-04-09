import pandas as pd
import numpy as np

from guardrail_ai.wdag.node import Node
from guardrail_ai.wdag.graph import WDAG
from guardrail_ai.wdag.executor import WDAGExecutor
from guardrail_ai.core.vitals_engine import VitalsEngine
from sklearn.preprocessing import StandardScaler

# -----------------------------
# 1️⃣ Simulated Regression Dataset
# -----------------------------
np.random.seed(42)

df = pd.DataFrame({
    "age": np.random.randint(20, 60, 100),
    "income": np.random.randint(30000, 100000, 100),
    "gender": np.random.choice(["M", "F"], 100),
    "prediction": np.random.uniform(0.5, 1.0, 100),
})
scaler = StandardScaler()

df_clean = df.copy()

df_clean[["age", "income"]] = scaler.fit_transform(
    df_clean[["age", "income"]]
)

# -----------------------------
# 2️⃣ Metadata
# -----------------------------
metadata = {
    "feature_columns": ["age", "income"],
    "numerical_features": ["age", "income"],
    "categorical_features": ["gender"],
    "prediction_column": "prediction",
    "protected_attributes": {
        "type": "categorical",
        "columns": ["gender"]
    },
    "prediction_type": "probability",
    "quasi_identifier_columns": ["age", "income"],
    "domain": "standard",
    "shap_values": np.random.randn(100),
}

# -----------------------------
# 3️⃣ Baseline (training stats)
# -----------------------------
baseline = {
    "baseline_summary": {
        "gini": {"mean": 0.4, "std": 0.1},
        "psi": {"mean": 0.05, "std": 0.02},
        "linf": {"mean": 0.3, "std": 0.1},
        "ood_score": {"mean": 0.1, "std": 0.05},
        "privacy_score": {"mean": 0.6, "std": 0.1},
        "statistical_parity": {"mean": 0.2, "std": 0.1},
        "shap_importance": {"mean": 0.5, "std": 0.2},
    }
}

# -----------------------------
# 4️⃣ WDAG Setup
# -----------------------------
graph = WDAG()

data_node = Node("Data", "Data Engineer")
model_node = Node("Model", "ML Engineer")
deploy_node = Node("Deployment", "DevOps")

graph.add_node(data_node)
graph.add_node(model_node)
graph.add_node(deploy_node)

# Weighted edges (blast radius)
graph.add_edge("Data", "Model", weight=0.8)
graph.add_edge("Model", "Deployment", weight=0.9)

# -----------------------------
# 5️⃣ Engine + Executor
# -----------------------------
engine = VitalsEngine(baseline, metadata)
executor = WDAGExecutor(graph, engine)

# -----------------------------
# 6️⃣ Run Test
# -----------------------------
result = executor.run("Data", df_clean)

# -----------------------------
# 7️⃣ Output
# -----------------------------
print("\n===== WDAG RESULT =====")
print(result)

print("\n===== GRAPH STATE =====")
print(graph.to_dict())