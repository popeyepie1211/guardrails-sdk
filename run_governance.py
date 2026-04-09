import json
import os
import pandas as pd
import psycopg2
from datetime import datetime
from guardrail_ai.core.vitals_engine import VitalsEngine

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

# 3. Initialize engine
# --- UPDATED METADATA BLOCK ---
engine = VitalsEngine(
    baseline=baseline_config,
    metadata={
        "domain": "finance",
        "feature_columns": ["income", "credit_score"],
        "numerical_features": ["income", "credit_score"], # <--- Add this line
        "categorical_features": ["gender"],               # <--- Add this line
        "protected_attributes": {
            "type": "categorical",
            "columns": ["gender"]
        },
        "quasi_identifier_columns": ["gender"],
        "prediction_column": "prediction",
        "prediction_type": "binary"
    }
)

# 4. Execute
results = engine.compute_batch(df)
print("PSI:", results["metrics"]["psi"]["value"])
print("Parity:", results["metrics"]["statistical_parity"]["value"])

# 5. Export (UNCHANGED LOGIC)
dashboard_export = {
    "fairness": round(
        results["metrics"].get("statistical_parity", {}).get("value", 0.85) * 100, 1
    ),
    "stability": round(
        (1 - results["metrics"].get("psi", {}).get("value", 0.08)) * 100, 1
    ),
    "security": 68.0 if results["overall_status"] != "normal" else 95.0,
    "status": results["overall_status"],
    "latency": 410
}

os.makedirs("public", exist_ok=True)

with open("public/dashboard_data.json", "w") as f:
    json.dump(dashboard_export, f, indent=2)

print("Metrics calculated and saved to public/dashboard_data.json")
print(results)

# --- STEP 3: SAVE TO TIMESCALEDB ---
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
        (time, model_id, fairness, stability, security, privacy, transparency, status) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    # Extract values properly (THIS is where your original instructions were wrong)
    fairness = results["metrics"].get("statistical_parity", {}).get("value", 0.85)
    stability = 1 - results["metrics"].get("psi", {}).get("value", 0.08)
    security = 0.68 if results["overall_status"] != "normal" else 0.95
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
        results["overall_status"]
    )

    cursor.execute(postgres_insert_query, record_to_insert)
    connection.commit()

    print("✅ Audit Result saved to TimescaleDB")

except Exception as error:
    print(f"❌ Failed to save to database: {error}")

finally:
    if 'connection' in locals() and connection:
        cursor.close()
        connection.close()
