import json
import os
import pandas as pd
from guardrail_ai.core.vitals_engine import VitalsEngine

# 1. Mock input data
data = {
    "income": [50000, 60000, 120000, 45000, 55000, 110000],
    "credit_score": [650, 710, 800, 620, 690, 780],
    "gender": ["M", "F", "M", "F", "M", "F"],
    "prediction": [0, 1, 1, 0, 1, 1]
}
df = pd.DataFrame(data)

# 2. Baseline config
baseline_config = {
    "baseline_summary": {
        "gini": {"mean": 0.45, "std": 0.05},
        "psi": {"mean": 0.02, "std": 0.01},
        "l_inf": {"mean": 0.10, "std": 0.02},
        "privacy_score": {"mean": 0.90, "std": 0.03},
        "statistical_parity": {"mean": 0.85, "std": 0.05}
    }
}

# 3. Initialize engine
engine = VitalsEngine(
    baseline=baseline_config,
    metadata={
        "feature_columns": ["income", "credit_score"],
        "protected_attributes": {
            "type": "categorical",
            "columns": ["gender"]
        },
        "prediction_column": "prediction",
        "prediction_type": "binary"
    }
)

# 4. Execute
results = engine.compute_batch(df)

# 5. Export
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