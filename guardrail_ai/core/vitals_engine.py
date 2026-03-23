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

from guardrail_ai.core.validator import Validator
from guardrail_ai.core.threshold import ThresholdEvaluator
from guardrail_ai.core.exceptions import GuardrailException
from guardrail_ai.metrics.fairness import StatisticalParity,GiniCoefficient


class VitalsEngine:
    """
    Core orchestration engine for computing and evaluating model vitals.
    """

    METRIC_DIRECTIONS = {
        "statistical_parity": "upper",
        "gini": "upper",
        "psi": "upper",
        "l_inf": "lower",          # smaller robustness distance = bad
        "privacy_score": "upper",
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

        # Determine if fairness is enabled
        self.fairness_enabled = (
            self.metadata.get("protected_attributes") is not None
        )

        # Validate baseline dynamically
        Validator.validate_baseline(
            self.baseline,
            fairness_enabled=self.fairness_enabled,
        )

    # -----------------------------
    # Metadata Validation
    # -----------------------------
    def _validate_metadata(self) -> None:

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

    # -----------------------------
    # Public API
    # -----------------------------
    def compute_batch(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Compute all vitals for a batch and evaluate against thresholds.
        """

        # Validate batch using updated validator
        Validator.validate_batch(
            df=df,
            feature_columns=self.metadata["feature_columns"],
            prediction_column=self.metadata["prediction_column"],
            protected_attributes=self.metadata.get("protected_attributes"),
        )

        # -----------------------------
        # Compute Metrics (Stub)
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

            baseline_metric = self.baseline["baseline_summary"][metric_name]
            mean = baseline_metric["mean"]
            std = baseline_metric["std"]

            direction = self.METRIC_DIRECTIONS.get(metric_name, "upper")

            result = ThresholdEvaluator.evaluate(
                metric_name=metric_name,
                value=value,
                mean=mean,
                std=std,
                direction=direction,
            )

            evaluated[metric_name] = result

            if result["status"] == "critical":
                overall_status = "critical"
            elif result["status"] == "warning" and overall_status != "critical":
                overall_status = "warning"

        return {
            "metrics": evaluated,
            "overall_status": overall_status,
        }

    # -----------------------------
    # Temporary Stub Metrics
    # -----------------------------
    def _compute_metrics(self, df: pd.DataFrame) -> Dict[str, float]:

        summary = self.baseline["baseline_summary"]
        metrics = {}

    # Fairness
        if self.fairness_enabled:
            metrics["statistical_parity"] = StatisticalParity.compute(
            df=df,
            prediction_column=self.metadata["prediction_column"],
            protected_attributes=self.metadata["protected_attributes"],
        )
            # Gini coefficient for all prediction types (probability, binary, multiclass)
        preds = df[self.metadata["prediction_column"]].values

        metrics["gini"] = GiniCoefficient.compute(preds)
    # Remaining metrics (stub)
        for metric in summary:
            if metric in ["statistical_parity", "gini"]:
               continue
        metrics[metric] = summary[metric]["mean"]

        return metrics