import numpy as np
import pandas as pd

from guardrail_ai.core.baseline_initializer import BaselineInitializer
from guardrail_ai.core.vitals_engine import VitalsEngine
from guardrail_ai.wdag.graph import WDAG
from guardrail_ai.wdag.node import Node
from guardrail_ai.wdag.executor import WDAGExecutor
from guardrail_ai.digital_judge import DigitalJudge, GovernanceReportBuilder


baseline_df = pd.DataFrame({
    "f1": np.linspace(0.0, 1.0, 100),
    "f2": np.linspace(1.0, 2.0, 100),
    "prediction": np.linspace(0.2, 0.8, 100),
})

metadata = {
    "feature_columns": ["f1", "f2"],
    "numerical_features": ["f1", "f2"],
    "categorical_features": [],
    "prediction_column": "prediction",
    "protected_attributes": None,
    "prediction_type": "probability",
    "quasi_identifier_columns": ["f1"],
    "domain": "healthcare",
    "shap_values": np.zeros(100),
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

production_batch = pd.DataFrame({
    "f1": np.linspace(8.0, 10.0, 50),
    "f2": np.linspace(9.0, 11.0, 50),
    "prediction": np.linspace(0.1, 0.9, 50),
})

metadata["shap_values"] = np.ones(50) * 2.0

part_a_result = executor.run("Data", production_batch)

governance_result = {
    "model_id": "IntegrationDemo-v1",
    "domain": metadata["domain"],
    "threshold_results": part_a_result.get("metrics", {}),
    "metrics": part_a_result.get("metrics", {}),
    "wdag_status": {"nodes": graph.to_dict()},
}

judge = DigitalJudge()
decision = judge.judge(governance_result)

report_builder = GovernanceReportBuilder()
report = report_builder.build(decision, governance_result)

print("PART A STATUS:", part_a_result["status"])
print("PART B DIAGNOSIS:", decision["diagnosis"])
print("PART B SEVERITY:", decision["severity"])
print("PART B ACTION:", decision["recommended_action"])
print()
print(report_builder.render_text(report))