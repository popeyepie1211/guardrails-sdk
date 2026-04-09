import json
import os
import pandas as pd
import psycopg2
from datetime import datetime

# Core Engine Imports
from guardrail_ai.core.vitals_engine import VitalsEngine

# WDAG Execution Imports
from guardrail_ai.wdag.node import Node
from guardrail_ai.wdag.graph import WDAG
from guardrail_ai.wdag.executor import WDAGExecutor

# 1. Mock input data
data = {
    "income": [40000, 50000, 60000, 70000, 80000, 90000],
    "credit_score": [600, 650, 700, 720, 750, 780],
    "gender": ["M", "M", "M", "F", "F", "F"],
    "prediction": [1, 1, 1, 0, 0, 0]
}
df = pd.DataFrame(data)

# 2. Baseline config
baseline_config = {
    "baseline_summary": {
        "gini": {"mean": 0.45, "std": 0.05},
        "psi": {"mean": 0.02, "std": 0.01},
        "linf": {"mean": 50000, "std": 10000},
        "privacy_score": {"mean": 0.90, "std": 0.03},
        "statistical_parity": {"mean": 0.85, "std": 0.05},
        "ood_score": {"mean": 0.80, "std": 0.05},
        "shap_importance": {"mean": 0.50, "std": 0.10},
    }
}

# 3. Initialize engine & metadata
engine = VitalsEngine(
    baseline=baseline_config,
    metadata={
        "domain": "finance",
        "feature_columns": ["income", "credit_score"],
        "numerical_features": ["income", "credit_score"],
        "categorical_features": ["gender"],
        "protected_attributes": {
            "type": "categorical",
            "columns": ["gender"]
        },
        "quasi_identifier_columns": ["gender"],
        "prediction_column": "prediction",
        "prediction_type": "binary"
    }
)

# 4. Initialize WDAG Graph
graph = WDAG()
data_node = Node("Data_Stream", "Data Engineer")
intercept_node = Node("SDK_Intercept", "Middleware")
vitals_node = Node("Vitals_Engine", "Analysis")

graph.add_node(data_node)
graph.add_node(intercept_node)
graph.add_node(vitals_node)

# Connect edges with blast radius weights
graph.add_edge("Data_Stream", "SDK_Intercept", weight=1.0)
graph.add_edge("SDK_Intercept", "Vitals_Engine", weight=1.0)

# 5. Execute Graph
executor = WDAGExecutor(graph, engine)
results = executor.run("Data_Stream", df)

print("===== WDAG RESULT =====")
print(f"Overall Status: {results['status']}")

# Extract the graph trace to JSON for the database
wdag_trace_json = json.dumps(graph.to_dict())

# 6. Save to TimescaleDB
try:
    connection = psycopg2.connect(
        user="postgres",
        password="password",
        host="127.0.0.1",
        port="5432",
        database="postgres"
    )
    cursor = connection.cursor()

    postgres_insert_query = """
        INSERT INTO model_vitals 
        (time, model_id, fairness, stability, security, privacy, transparency, status, wdag_trace) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    # Extract metrics safely
    fairness = results["metrics"].get("statistical_parity", {}).get("value", 0.85)
    stability = 1 - results["metrics"].get("psi", {}).get("value", 0.08)
    security = 0.68 if results["status"] != "normal" else 0.95
    privacy = results["metrics"].get("privacy_score", {}).get("value", 0.90)
    transparency = results["metrics"].get("gini", {}).get("value", 0.45)

    record_to_insert = (
        datetime.now(),
        "loan_model_v1",
        fairness,
        stability,
        security,
        privacy,
        transparency,
        results["status"],
        wdag_trace_json  # Included graph trace here
    )

    cursor.execute(postgres_insert_query, record_to_insert)
    connection.commit()

    print("✅ Audit Result & WDAG Trace saved to TimescaleDB")

except Exception as error:
    print(f"❌ Failed to save to database: {error}")

finally:
    if 'connection' in locals() and connection:
        cursor.close()
        connection.close()