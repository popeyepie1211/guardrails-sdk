from typing import Dict, Any
import pandas as pd
import numpy as np


class BaselineInitializer:
    """
    Computes baseline statistics and reference distributions
    from training data.
    """

    def __init__(self, df: pd.DataFrame, metadata: Dict[str, Any]) -> None:
        self.df = df
        self.metadata = metadata

    def compute(self) -> Dict[str, Any]:

        numerical_features = self.metadata["numerical_features"]
        prediction_col = self.metadata["prediction_column"]

        baseline_summary = {}

        # -----------------------------
        # Gini baseline
        # -----------------------------
        preds = self.df[prediction_col].values
        baseline_summary["gini"] = {
            "mean": float(np.mean(preds)),
            "std": float(np.std(preds)),
        }

        # -----------------------------
        # PSI baseline (store distributions)
        # -----------------------------
        psi_distributions = {}

        for col in numerical_features:
            psi_distributions[col] = self.df[col].values

        baseline_summary["psi"] = {
            "mean": 0.1,   # default stable value
            "std": 0.05,
        }

        # -----------------------------
        # L∞ + OOD baseline
        # -----------------------------
        baseline_summary["linf"] = {
            "mean": 0.2,
            "std": 0.1,
        }

        baseline_summary["ood_score"] = {
            "mean": 0.1,
            "std": 0.05,
        }

        # -----------------------------
        # Privacy baseline
        # -----------------------------
        baseline_summary["privacy_score"] = {
            "mean": 0.7,
            "std": 0.1,
        }

        # -----------------------------
        # Fairness baseline (optional)
        # -----------------------------
        if self.metadata.get("protected_attributes"):
            baseline_summary["statistical_parity"] = {
                "mean": 0.2,
                "std": 0.1,
            }

        # -----------------------------
        # SHAP baseline (optional)
        # -----------------------------
        baseline_summary["shap_importance"] = {
            "mean": 0.5,
            "std": 0.2,
        }

        # -----------------------------
        # Final baseline object
        # -----------------------------
        baseline = {
            "baseline_summary": baseline_summary,
            "distributions": {
                "numerical": psi_distributions
            }
        }

        return baseline