"""
core/validator.py

Validation logic for Guardrail AI Monitoring Engine.
Ensures baseline structure and incoming batch data integrity.
"""


from typing import Dict, List, Optional, Any
import pandas as pd

from guardrail_ai.core.exceptions import (
    BaselineValidationError,
    InputValidationError,
)


class Validator:
    """
    Provides static validation methods for baseline and input data.
    """

    # -----------------------------
    # Baseline Validation
    # -----------------------------
    @staticmethod
    def validate_baseline(
        baseline: Dict,
        fairness_enabled: bool,
    ) -> None:
        """
        Validate baseline_summary structure.
        Fairness metric is required only if fairness_enabled = True.
        """

        if not isinstance(baseline, dict):
            raise BaselineValidationError("Baseline must be a dictionary.")

        if "baseline_summary" not in baseline:
            raise BaselineValidationError("Missing 'baseline_summary' key.")

        summary = baseline["baseline_summary"]

        if not isinstance(summary, dict):
            raise BaselineValidationError("'baseline_summary' must be a dictionary.")

        # Core required metrics (always required)
        required_metrics = [
            "gini",
            "psi",
            "linf",
            "ood_score",
            "privacy_score",
            "shap_importance",
        ]

        # Add fairness only if enabled
        if fairness_enabled:
            required_metrics.append("statistical_parity")

        for metric in required_metrics:
            if metric not in summary:
                raise BaselineValidationError(
                    f"Missing required metric '{metric}' in baseline."
                )

            metric_data = summary[metric]

            if not isinstance(metric_data, dict):
                raise BaselineValidationError(
                    f"Metric '{metric}' must contain 'mean' and 'std'."
                )

            if "mean" not in metric_data or "std" not in metric_data:
                raise BaselineValidationError(
                    f"Metric '{metric}' must include 'mean' and 'std'."
                )

            mean = metric_data["mean"]
            std = metric_data["std"]

            if not isinstance(mean, (int, float)):
                raise BaselineValidationError(
                    f"Mean for '{metric}' must be numeric."
                )

            if not isinstance(std, (int, float)):
                raise BaselineValidationError(
                    f"Std for '{metric}' must be numeric."
                )

            if std < 0:
                raise BaselineValidationError(
                    f"Std for '{metric}' cannot be negative."
                )
    
    @staticmethod
    def validate_batch(
    df: pd.DataFrame,
    feature_columns: List[str],
    prediction_column: str,
    protected_attributes: Optional[Dict[str, Any]],
    quasi_identifier_columns: List[str],
    numerical_features: List[str],
    categorical_features: List[str],
    domain: str,
    ) -> None:
    

    # -----------------------------
    # Domain Validation
    # -----------------------------
        SUPPORTED_DOMAINS = {"healthcare", "finance", "standard"}

        if domain not in SUPPORTED_DOMAINS:
           raise InputValidationError(
            f"Invalid domain '{domain}'. Supported domains: {SUPPORTED_DOMAINS}"
        )

    # -----------------------------
    # Basic DataFrame checks
    # -----------------------------
        if not isinstance(df, pd.DataFrame):
            raise InputValidationError("Input must be a pandas DataFrame.")

        if df.empty:
            raise InputValidationError("Input DataFrame is empty.")

        if df.columns.duplicated().any():
           raise InputValidationError("Duplicate columns detected in DataFrame.")

    # -----------------------------
    # Feature consistency
    # -----------------------------
        for col in feature_columns:
            if col not in df.columns:
               raise InputValidationError(
                f"Feature column '{col}' missing in data."
            )

    # Prevent overlap
        overlap = set(numerical_features) & set(categorical_features)
        if overlap:
           raise InputValidationError(
            f"Columns cannot be both numerical and categorical: {overlap}"
        )

    # -----------------------------
    # Numerical features
    # -----------------------------
        for col in numerical_features:
            if col not in df.columns:
               raise InputValidationError(
                f"Numerical feature '{col}' missing in data."
            )

            if not pd.api.types.is_numeric_dtype(df[col]):
               raise InputValidationError(
                f"Numerical feature '{col}' must be numeric."
            )

    # -----------------------------
    # Categorical features
    # -----------------------------
        for col in categorical_features:
            if col not in df.columns:
               raise InputValidationError(
                f"Categorical feature '{col}' missing in data."
            )

    # -----------------------------
    # Quasi-identifiers (FIXED)
    # -----------------------------
        for col in quasi_identifier_columns:
            if col not in df.columns:
               raise InputValidationError(
                f"Quasi identifier column '{col}' missing in data."
            )

            if df[col].isnull().all():
               raise InputValidationError(
                f"Quasi identifier column '{col}' contains only null values."
            )

    # -----------------------------
    # Required columns
    # -----------------------------
        required_columns = feature_columns + [prediction_column]

        if protected_attributes is not None:
           protected_columns = protected_attributes.get("columns", [])
           required_columns += protected_columns

        missing_columns = [
           col for col in required_columns if col not in df.columns
    ]

        if missing_columns:
           raise InputValidationError(
            f"Missing required columns: {missing_columns}"
        )

    # -----------------------------
    # Null checks
    # -----------------------------
        for col in required_columns:
            if df[col].isnull().all():
               raise InputValidationError(
                f"Column '{col}' contains only null values."
            )

    # -----------------------------
    # Prediction column checks
    # -----------------------------
        if df[prediction_column].isnull().any():
            raise InputValidationError(
            f"Prediction column '{prediction_column}' contains null values."
        )

        if not pd.api.types.is_numeric_dtype(df[prediction_column]):
            raise InputValidationError(
            f"Prediction column '{prediction_column}' must be numeric."
        )

    # -----------------------------
    # Protected attributes (optional)
    # -----------------------------
        if protected_attributes is not None:

            attr_type = protected_attributes.get("type")
            columns = protected_attributes.get("columns", [])

            if attr_type not in ("categorical", "one_hot"):
               raise InputValidationError(
                "Protected attribute type must be 'categorical' or 'one_hot'."
            )

            if not isinstance(columns, list) or len(columns) == 0:
               raise InputValidationError(
                "Protected attribute 'columns' must be a non-empty list."
            )

        # -----------------------------
        # CATEGORICAL
        # -----------------------------
            if attr_type == "categorical":

                if len(columns) != 1:
                   raise InputValidationError(
                    "Categorical protected attribute must contain exactly one column."
                )

                col = columns[0]

                unique_values = df[col].dropna().unique()

                if len(unique_values) < 2:
                   raise InputValidationError(
                    f"Protected attribute '{col}' must contain at least two groups."
                )

                if len(unique_values) > 20:
                   raise InputValidationError(
                    f"Protected attribute '{col}' has too many unique values."
                )

        # -----------------------------
        # ONE-HOT
        # -----------------------------
            elif attr_type == "one_hot":

                if len(columns) < 2:
                   raise InputValidationError(
                    "One-hot protected attributes must contain at least two columns."
                )

                for col in columns:
                    if not set(df[col].dropna().unique()).issubset({0, 1}):
                       raise InputValidationError(
                        f"One-hot column '{col}' must contain only 0/1 values."
                    )

                if not (df[columns].sum(axis=1) == 1).all():
                    raise InputValidationError(
                    "Invalid one-hot encoding: each row must belong to exactly one group."
                )