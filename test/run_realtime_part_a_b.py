import numpy as np
import pandas as pd
from sklearn.datasets import load_diabetes
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

from guardrail_ai.core.baseline_initializer import BaselineInitializer
from guardrail_ai.core.batch_manager import BatchManager
from guardrail_ai.core.vitals_engine import VitalsEngine
from guardrail_ai.wdag.graph import WDAG
from guardrail_ai.wdag.node import Node
from guardrail_ai.wdag.executor import WDAGExecutor
from guardrail_ai.digital_judge import DigitalJudge, GovernanceReportBuilder


np.random.seed(42)

dataset = load_diabetes(as_frame=True)
X = dataset.frame.drop(columns=["target"])
y = dataset.frame["target"]

X_train, X_prod, y_train, y_prod = train_test_split(
    X,
    y,
    test_size=0.35,
    random_state=42,
)

model = RandomForestRegressor(n_estimators=50, random_state=42)
model.fit(X_train, y_train)

feature_columns = list(X.columns)
prediction_column = "prediction"

baseline_df = X_train.copy()
baseline_df[prediction_column] = model.predict(X_train)

metadata = {
    "feature_columns": feature_columns,
    "numerical_features": feature_columns,
    "categorical_features": [],
    "prediction_column": prediction_column,
    "protected_attributes": None,
    "prediction_type": "regression",
    "quasi_identifier_columns": ["age", "bmi"],
    "domain": "healthcare",
    "shap_values": None,
}

baseline = BaselineInitializer(baseline_df, metadata).compute()
engine = VitalsEngine(baseline=baseline, metadata=metadata)

graph = WDAG()
graph.add_node(Node("Data", "Data Governance Team"))
graph.add_node(Node("Model", "ML Owner"))
graph.add_node(Node("Deployment", "Platform Team"))

graph.add_edge("Data", "Model")
graph.add_edge("Model", "Deployment")

executor = WDAGExecutor(graph, engine)
judge = DigitalJudge()
report_builder = GovernanceReportBuilder()

batch_manager = BatchManager(
    batch_size=40,
    min_batch_size=20,
    timeout_seconds=30,
)

production_df = X_prod.copy().reset_index(drop=True)

print("\nStreaming real diabetes dataset through Part A + Part B...\n")

latest_report = None
batch_number = 0

for start in range(0, len(production_df), 10):
    chunk = production_df.iloc[start:start + 10].copy()

    # Simulate production drift in later streaming batches.
    if start >= len(production_df) // 2:
        chunk["bmi"] = chunk["bmi"] * 4.0 + 0.4
        chunk["s5"] = chunk["s5"] * 3.0 + 0.3

    chunk[prediction_column] = model.predict(chunk[feature_columns])

    batch = batch_manager.add(chunk)

    if batch is None:
        continue

    batch_number += 1

    # In real deployment this can come from SDK / worker SHAP computation.
    # Keeping it stable here so drift/security signals are easier to inspect.
    metadata["shap_values"] = np.zeros(len(batch))

    part_a_result = executor.run("Data", batch)

    governance_result = {
        "model_id": "DiabetesRisk-Regressor-v1",
        "domain": metadata["domain"],
        "environment": "Real-Time Simulation",
        "threshold_results": part_a_result.get("metrics", {}),
        "metrics": part_a_result.get("metrics", {}),
        "wdag_status": {
            "nodes": graph.to_dict(),
        },
    }

    decision = judge.judge(governance_result)
    latest_report = report_builder.build(decision, governance_result)

    print(
        f"Batch {batch_number}: "
        f"Part A={part_a_result['status']} | "
        f"Diagnosis={decision['diagnosis']} | "
        f"Severity={decision['severity']} | "
        f"Action={decision['recommended_action']}"
    )

final_batch = batch_manager.flush()

if final_batch is not None:
    batch_number += 1
    metadata["shap_values"] = np.zeros(len(final_batch))

    part_a_result = executor.run("Data", final_batch)

    governance_result = {
        "model_id": "DiabetesRisk-Regressor-v1",
        "domain": metadata["domain"],
        "environment": "Real-Time Simulation",
        "threshold_results": part_a_result.get("metrics", {}),
        "metrics": part_a_result.get("metrics", {}),
        "wdag_status": {
            "nodes": graph.to_dict(),
        },
    }

    decision = judge.judge(governance_result)
    latest_report = report_builder.build(decision, governance_result)

    print(
        f"Batch {batch_number}: "
        f"Part A={part_a_result['status']} | "
        f"Diagnosis={decision['diagnosis']} | "
        f"Severity={decision['severity']} | "
        f"Action={decision['recommended_action']}"
    )

if latest_report:
    print("\nFINAL GOVERNANCE REPORT\n")
    print(report_builder.render_text(latest_report))