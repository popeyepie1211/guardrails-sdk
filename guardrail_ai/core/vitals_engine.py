"""
core/vitals_engine.py

Main orchestration engine for Guardrail AI.
Handles:
- Baseline validation
- Metadata-driven batch validation
- Metric execution (stubbed for now)
- Threshold evaluation
- Status aggregation
"""

from typing import Dict, Any
import pandas as pd
import numpy as np
from guardrail_ai import metrics
from guardrail_ai.core.persistence import PersistenceManager
from guardrail_ai.core.validator import Validator
from guardrail_ai.core.threshold import ThresholdEvaluator
from guardrail_ai.core.exceptions import GuardrailException
from guardrail_ai.metrics.fairness import StatisticalParity, GiniCoefficient
from guardrail_ai.metrics.privacy import PrivacyScore
from guardrail_ai.metrics.stability import PSI
from guardrail_ai.metrics.transparency import SHAPExplainability
from guardrail_ai.metrics.security import Security


class VitalsEngine:
    """
    Core orchestration engine for computing and evaluating model vitals.
    """

    METRIC_DIRECTIONS = {
        "statistical_parity": "upper",
        "gini": "upper",
        "psi": "upper",
        "linf": "lower",
        "ood_score": "upper",
        "privacy_score": "upper",
        "shap_importance": "upper",
    }

    def __init__(self, baseline: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """
        Initialize engine with:
        - baseline statistics
        - model metadata
        """

        self.baseline = baseline
        self.metadata = metadata

        # Validate metadata first
        self._validate_metadata()
        self.prediction_type = self.metadata["prediction_type"]
        self.domain = self.metadata["domain"]
        self.numerical_features = self.metadata["numerical_features"]
        self.categorical_features = self.metadata["categorical_features"]

        # Determine if fairness is enabled
        self.fairness_enabled = self.metadata.get("protected_attributes") is not None

        # Validate baseline dynamically
        Validator.validate_baseline(
            self.baseline,
            fairness_enabled=self.fairness_enabled,
        )
        self.persistence = PersistenceManager()
    # -----------------------------
    # Metadata Validation
    # -----------------------------
    def _validate_metadata(self) -> None:
        if "domain" not in self.metadata:
            raise GuardrailException("Missing 'domain' in metadata")

        if not isinstance(self.metadata, dict):
            raise GuardrailException("Metadata must be a dictionary.")

        if "feature_columns" not in self.metadata:
            raise GuardrailException("Missing 'feature_columns' in metadata.")

        if "prediction_column" not in self.metadata:
            raise GuardrailException("Missing 'prediction_column' in metadata.")

        if not isinstance(self.metadata["feature_columns"], list):
            raise GuardrailException("'feature_columns' must be a list.")

        if not isinstance(self.metadata["prediction_column"], str):
            raise GuardrailException("'prediction_column' must be a string.")

        # Metadata for privacy score
        if "quasi_identifier_columns" not in self.metadata:
            raise GuardrailException("Missing 'quasi_identifier_columns' in metadata.")

        if not isinstance(self.metadata["quasi_identifier_columns"], list):
            raise GuardrailException("'quasi_identifier_columns' must be a list.")

        if len(self.metadata["quasi_identifier_columns"]) == 0:
            raise GuardrailException("'quasi_identifier_columns' cannot be empty.")
        # prediction type validation
        valid_types = ["probability", "binary", "multiclass"]

        if self.metadata["prediction_type"] not in valid_types:
            raise GuardrailException(
                f"prediction_type must be one of {valid_types} and Warning: Binary predictions reduce metric sensitivity.Please provide probabilities not raw labels."
            )

        # Protected attributes are optional
        protected = self.metadata.get("protected_attributes")

        if protected is not None:
            if not isinstance(protected, dict):
                raise GuardrailException(
                    "'protected_attributes' must be a dictionary or None."
                )

            if "type" not in protected or "columns" not in protected:
                raise GuardrailException(
                    "Protected attributes must contain 'type' and 'columns'."
                )
    
        if "numerical_features" not in self.metadata:
            raise GuardrailException("Missing 'numerical_features' in metadata.")

        if not isinstance(self.metadata["numerical_features"], list):
           raise GuardrailException("'numerical_features' must be a list.")

        if len(self.metadata["numerical_features"]) == 0:
           raise GuardrailException("'numerical_features' cannot be empty.")
        if "categorical_features" not in self.metadata:
           raise GuardrailException("Missing 'categorical_features' in metadata.")

        if not isinstance(self.metadata["categorical_features"], list):
           raise GuardrailException("'categorical_features' must be a list.")

    # -----------------------------
    # Public API
    # -----------------------------
    def compute_batch(self, df: pd.DataFrame) -> Dict[str, Any]:

    # -----------------------------
    # Validate batch
    # -----------------------------
        Validator.validate_batch(
        df=df,
        feature_columns=self.metadata["feature_columns"],
        prediction_column=self.metadata["prediction_column"],
        protected_attributes=self.metadata.get("protected_attributes"),
        quasi_identifier_columns=self.metadata["quasi_identifier_columns"],
        numerical_features=self.metadata["numerical_features"],
        categorical_features=self.metadata["categorical_features"],
        domain=self.domain,
        )

    # -----------------------------
    # Compute Metrics
    # -----------------------------
        metrics = self._compute_metrics(df)

    # -----------------------------
    # Apply Thresholds
    # -----------------------------
        evaluated = {}
        overall_status = "normal"

        for metric_name, value in metrics.items():

        # Skip fairness if disabled
            if metric_name == "statistical_parity" and not self.fairness_enabled:
               continue

        # SAFE baseline access
            if metric_name not in self.baseline["baseline_summary"]:
                evaluated[metric_name] = {
                "value": value,
                "status": "no_baseline"
            }
                continue

            baseline_metric = self.baseline["baseline_summary"][metric_name]
            mean = baseline_metric["mean"]
            std = baseline_metric["std"]

            direction = self.METRIC_DIRECTIONS.get(metric_name, "upper")
            history = self.persistence.get_history(metric_name)
            
            result = ThresholdEvaluator.evaluate(
            metric_name=metric_name,
            value=value,
            mean=mean,
            std=std,
            direction=direction,
            history=history,
            domain=self.domain,
            
        )

            evaluated[metric_name] = result

            if result["status"] == "critical":
               overall_status = "critical"
            elif result["status"] == "warning" and overall_status != "critical":
               overall_status = "warning"
            self.persistence.save_metric_status(
              metric_name,
              result["status"]
)        
       
        return {
        "metrics": evaluated,
        "overall_status": overall_status,
    }
    def compute_psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    

        expected = np.asarray(expected)
        actual = np.asarray(actual)

    # Create bins from expected distribution
        bin_edges = np.histogram_bin_edges(expected, bins=bins)

    # Histogram counts
        expected_counts, _ = np.histogram(expected, bins=bin_edges)
        actual_counts, _ = np.histogram(actual, bins=bin_edges)

    # Convert to proportions
        expected_perc = expected_counts / len(expected)
        actual_perc = actual_counts / len(actual)

    # Avoid division by zero
        epsilon = 1e-6
        expected_perc = np.where(expected_perc == 0, epsilon, expected_perc)
        actual_perc = np.where(actual_perc == 0, epsilon, actual_perc)

    # PSI formula
        psi = np.sum((actual_perc - expected_perc) * np.log(actual_perc / expected_perc))

        return float(psi)
    
    
    def _compute_metrics(self, df: pd.DataFrame) -> Dict[str, float]:

        metrics = {}

    # -----------------------------
    # Fairness (Optional)
    # -----------------------------
        if self.fairness_enabled:
            metrics["statistical_parity"] = StatisticalParity.compute(
            df=df,
            prediction_column=self.metadata["prediction_column"],
            protected_attributes=self.metadata["protected_attributes"],
        )

    # -----------------------------
    # Predictions
    # -----------------------------
        preds = df[self.metadata["prediction_column"]].values

    # -----------------------------
    # Gini
    # -----------------------------
        metrics["gini"] = GiniCoefficient.compute(preds)

    # -----------------------------
    # Privacy
    # -----------------------------
        metrics["privacy_score"] = PrivacyScore.compute(
        df,
        self.metadata["quasi_identifier_columns"]
    )

    # -----------------------------
    # PSI (numerical features)
    # -----------------------------
        psi_values = []

        for col in self.metadata["numerical_features"]:
            expected = self.baseline["distributions"]["numerical"][col]
            actual = df[col].values


            psi_col = PSI.compute_psi(expected, actual)
            psi_values.append(psi_col)
            
        metrics["psi"] = float(np.mean(psi_values)) if psi_values else 0.0
        metrics["psi"] = min(metrics["psi"], 1.0)
    # -----------------------------
    # Security: L∞
    # -----------------------------
        linf_values = []

        for col in self.metadata["numerical_features"]:
            actual = df[col].values
            expected = self.baseline["distributions"]["numerical"][col]

            std = np.std(expected) + 1e-6
            linf = np.max(np.abs(actual - np.mean(expected))) / std
            linf_values.append(linf)

        metrics["linf"] = float(np.mean(linf_values)) if linf_values else 0.0


        # -----------------------------
        # OOD Score
        # -----------------------------
        ood_values = []

        for col in self.metadata["numerical_features"]:
            actual = df[col].values
            expected = self.baseline["distributions"]["numerical"][col]

            mean = np.mean(expected)
            std = np.std(expected) + 1e-6

            z_scores = np.abs((actual - mean) / std)
            ood_ratio = np.mean(z_scores > 3)  # % outliers

            ood_values.append(ood_ratio)

        metrics["ood_score"] = float(np.mean(ood_values)) if ood_values else 0.0

    # -----------------------------
    # SHAP (Batch-based)
    # -----------------------------
        shap_values = self.metadata.get("shap_values")

        if shap_values is not None:
            metrics["shap_importance"] = SHAPExplainability.compute(shap_values)
        else:
            metrics["shap_importance"] = 0.0

        return metrics