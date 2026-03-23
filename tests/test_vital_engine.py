import pytest
import pandas as pd

from guardrail_ai.core.vitals_engine import VitalsEngine


# ----------------------------------
# Helpers
# ----------------------------------

def baseline_with_fairness():
    # SPD mean set to 0.0 so balanced data stays normal
    return {
        "baseline_summary": {
            "gini": {"mean": 0.3, "std": 0.02},
            "psi": {"mean": 0.05, "std": 0.01},
            "l_inf": {"mean": 0.2, "std": 0.01},
            "privacy_score": {"mean": 0.9, "std": 0.02},
            "statistical_parity": {"mean": 0.0, "std": 0.01},
        }
    }


def baseline_without_fairness():
    return {
        "baseline_summary": {
            "gini": {"mean": 0.3, "std": 0.02},
            "psi": {"mean": 0.05, "std": 0.01},
            "l_inf": {"mean": 0.2, "std": 0.01},
            "privacy_score": {"mean": 0.9, "std": 0.02},
        }
    }


def metadata_with_fairness():
    return {
        "feature_columns": ["feature1", "feature2"],
        "prediction_column": "prediction",
        "prediction_type": "binary",
        "protected_attributes": {
            "type": "categorical",
            "columns": ["gender"],
        },
    }


def metadata_without_fairness():
    return {
        "feature_columns": ["feature1", "feature2"],
        "prediction_column": "prediction",
        "prediction_type": "probability",
        "protected_attributes": None,
    }


def sample_dataframe():
    # Balanced groups → SPD = 0.0
    return pd.DataFrame({
        "feature1": [1, 2, 3, 4],
        "feature2": [5, 6, 7, 8],
        "prediction": [0.5, 0.5, 0.5, 0.5],
        "gender": ["M", "M", "F", "F"],
    })


# ----------------------------------
# Normal Flow
# ----------------------------------

def test_compute_batch_normal_with_fairness():
    engine = VitalsEngine(
        baseline=baseline_with_fairness(),
        metadata=metadata_with_fairness(),
    )

    result = engine.compute_batch(sample_dataframe())

    assert result["overall_status"] in ["normal", "warning"]
    assert "statistical_parity" in result["metrics"]


def test_compute_batch_without_fairness():
    engine = VitalsEngine(
        baseline=baseline_without_fairness(),
        metadata=metadata_without_fairness(),
    )

    result = engine.compute_batch(sample_dataframe())

    assert result["overall_status"] == "normal"
    assert "statistical_parity" not in result["metrics"]


# ----------------------------------
# Threshold Escalation
# ----------------------------------

def test_overall_status_escalation(monkeypatch):
    engine = VitalsEngine(
        baseline=baseline_with_fairness(),
        metadata=metadata_with_fairness(),
    )

    # Force gini far beyond threshold
    def fake_metrics(_):
        return {
            "gini": 10.0,  # way above baseline
            "psi": 0.05,
            "l_inf": 0.2,
            "privacy_score": 0.9,
            "statistical_parity": 0.0,
        }

    monkeypatch.setattr(engine, "_compute_metrics", fake_metrics)

    result = engine.compute_batch(sample_dataframe())

    assert result["overall_status"] == "critical"