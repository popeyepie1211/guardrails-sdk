import pytest
import pandas as pd

from guardrail_ai.core.validator import Validator
from guardrail_ai.core.exceptions import (
    BaselineValidationError,
    InputValidationError,
)


# -----------------------------------
# Helper Baseline Builders
# -----------------------------------

def baseline_with_fairness():
    return {
        "baseline_summary": {
            "gini": {"mean": 0.3, "std": 0.02},
            "psi": {"mean": 0.05, "std": 0.01},
            "linf": {"mean": 0.2, "std": 0.01},
            "ood_score": {"mean": 0.05, "std": 0.01},
            "privacy_score": {"mean": 0.9, "std": 0.02},
            "statistical_parity": {"mean": 0.1, "std": 0.01},
            "shap_importance": {"mean": 0.5, "std": 0.01},
        }
    }


def baseline_without_fairness():
    return {
        "baseline_summary": {
            "gini": {"mean": 0.3, "std": 0.02},
            "psi": {"mean": 0.05, "std": 0.01},
            "linf": {"mean": 0.2, "std": 0.01},
            "ood_score": {"mean": 0.05, "std": 0.01},
            "privacy_score": {"mean": 0.9, "std": 0.02},
            "shap_importance": {"mean": 0.5, "std": 0.01},
        }
    }


# -----------------------------------
# Baseline Tests
# -----------------------------------

def test_valid_baseline_with_fairness():
    Validator.validate_baseline(
        baseline_with_fairness(),
        fairness_enabled=True,
    )


def test_missing_fairness_metric_when_enabled():
    with pytest.raises(BaselineValidationError):
        Validator.validate_baseline(
            baseline_without_fairness(),
            fairness_enabled=True,
        )


def test_valid_baseline_without_fairness():
    Validator.validate_baseline(
        baseline_without_fairness(),
        fairness_enabled=False,
    )


def test_negative_std_raises():
    bad = baseline_with_fairness()
    bad["baseline_summary"]["gini"]["std"] = -1

    with pytest.raises(BaselineValidationError):
        Validator.validate_baseline(bad, fairness_enabled=True)


# -----------------------------------
# Batch Tests
# -----------------------------------

def sample_dataframe():
    return pd.DataFrame({
        "feature1": [1, 2, 3],
        "feature2": [4, 5, 6],
        "prediction": [0, 1, 0],
        "gender": ["M", "F", "M"],
        "gender_m": [1, 0, 1],
        "gender_f": [0, 1, 0],
    })


def test_valid_batch_no_fairness():
    df = sample_dataframe()

    Validator.validate_batch(
        df=df,
        feature_columns=["feature1", "feature2"],
        prediction_column="prediction",
        protected_attributes=None,
        quasi_identifier_columns=["feature1"],
        numerical_features=["feature1", "feature2"],
        categorical_features=["gender"]
    )


def test_missing_required_column():
    df = sample_dataframe().drop(columns=["feature1"])

    with pytest.raises(InputValidationError):
        Validator.validate_batch(
            df=df,
            feature_columns=["feature1", "feature2"],
            prediction_column="prediction",
            protected_attributes=None,
            quasi_identifier_columns=["feature1"],
            numerical_features=["feature1", "feature2"],
            categorical_features=["gender"]
        )


def test_prediction_contains_null():
    df = sample_dataframe()
    df.loc[0, "prediction"] = None

    with pytest.raises(InputValidationError):
        Validator.validate_batch(
            df=df,
            feature_columns=["feature1", "feature2"],
            prediction_column="prediction",
            protected_attributes=None,
            quasi_identifier_columns=["feature1"],
            numerical_features=["feature1", "feature2"],
            categorical_features=["gender"]
        )


# -----------------------------------
# Categorical Protected Attribute
# -----------------------------------

def test_valid_categorical_protected_attribute():
    df = sample_dataframe()

    Validator.validate_batch(
        df=df,
        feature_columns=["feature1", "feature2"],
        prediction_column="prediction",
        protected_attributes={
            "type": "categorical",
            "columns": ["gender"],
        },
        quasi_identifier_columns=["feature1"],
        numerical_features=["feature1", "feature2"],
        categorical_features=["gender"]
    )


def test_categorical_less_than_two_groups():
    df = sample_dataframe()
    df["gender"] = "M"

    with pytest.raises(InputValidationError):
        Validator.validate_batch(
            df=df,
            feature_columns=["feature1", "feature2"],
            prediction_column="prediction",
            protected_attributes={
                "type": "categorical",
                "columns": ["gender"],
            },
            quasi_identifier_columns=["feature1"],
            numerical_features=["feature1", "feature2"],
            categorical_features=["gender"]
        )


# -----------------------------------
# One-Hot Protected Attribute
# -----------------------------------

def test_valid_one_hot_protected_attribute():
    df = sample_dataframe()

    Validator.validate_batch(
        df=df,
        feature_columns=["feature1", "feature2"],
        prediction_column="prediction",
        protected_attributes={
            "type": "one_hot",
            "columns": ["gender_m", "gender_f"],
        },
        quasi_identifier_columns=["feature1"],
        numerical_features=["feature1", "feature2"],
        categorical_features=["gender"]
    )


def test_invalid_one_hot_values():
    df = sample_dataframe()
    df["gender_m"] = [2, 0, 1]  # invalid value

    with pytest.raises(InputValidationError):
        Validator.validate_batch(
            df=df,
            feature_columns=["feature1", "feature2"],
            prediction_column="prediction",
            protected_attributes={
                "type": "one_hot",
                "columns": ["gender_m", "gender_f"],
            },
            quasi_identifier_columns=["feature1"],
            numerical_features=["feature1", "feature2"],
            categorical_features=["gender"]
        )


def test_invalid_protected_type():
    df = sample_dataframe()

    with pytest.raises(InputValidationError):
        Validator.validate_batch(
            df=df,
            feature_columns=["feature1", "feature2"],
            prediction_column="prediction",
            protected_attributes={
                "type": "numeric",
                "columns": ["gender"],
            },
            quasi_identifier_columns=["feature1"],
            numerical_features=["feature1", "feature2"],
            categorical_features=["gender"]
        )