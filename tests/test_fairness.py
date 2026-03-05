import pandas as pd
import pytest

from guardrail_ai.metrics.fairness import StatisticalParity


# -----------------------------
# 1️⃣ Balanced Groups (Categorical)
# -----------------------------
def test_statistical_parity_balanced():
    df = pd.DataFrame({
        "gender": ["M", "M", "F", "F"],
        "prediction": [1, 0, 1, 0],
    })

    result = StatisticalParity.compute(
        df=df,
        prediction_column="prediction",
        protected_attributes={
            "type": "categorical",
            "columns": ["gender"],
        },
    )

    assert result == 0.0


# -----------------------------
# 2️⃣ Extreme Bias (Categorical)
# -----------------------------
def test_statistical_parity_extreme_bias():
    df = pd.DataFrame({
        "gender": ["M", "M", "F", "F"],
        "prediction": [1, 1, 0, 0],
    })

    result = StatisticalParity.compute(
        df=df,
        prediction_column="prediction",
        protected_attributes={
            "type": "categorical",
            "columns": ["gender"],
        },
    )

    assert result == 1.0


# -----------------------------
# 3️⃣ Multi-Group Case
# -----------------------------
def test_statistical_parity_multigroup():
    df = pd.DataFrame({
        "group": ["A", "A", "B", "B", "C", "C"],
        "prediction": [1, 1, 0, 0, 1, 0],
    })

    result = StatisticalParity.compute(
        df=df,
        prediction_column="prediction",
        protected_attributes={
            "type": "categorical",
            "columns": ["group"],
        },
    )

    # A mean = 1.0
    # B mean = 0.0
    # C mean = 0.5
    # max diff = 1.0
    assert result == 1.0


# -----------------------------
# 4️⃣ One-Hot Valid Case
# -----------------------------
def test_statistical_parity_one_hot():
    df = pd.DataFrame({
        "male":   [1, 1, 0, 0],
        "female": [0, 0, 1, 1],
        "prediction": [1, 0, 1, 0],
    })

    result = StatisticalParity.compute(
        df=df,
        prediction_column="prediction",
        protected_attributes={
            "type": "one_hot",
            "columns": ["male", "female"],
        },
    )

    assert result == 0.0


# -----------------------------
# 5️⃣ Single Group Edge Case
# -----------------------------
def test_statistical_parity_single_group():
    df = pd.DataFrame({
        "gender": ["M", "M", "M"],
        "prediction": [1, 0, 1],
    })

    result = StatisticalParity.compute(
        df=df,
        prediction_column="prediction",
        protected_attributes={
            "type": "categorical",
            "columns": ["gender"],
        },
    )

    # Only one group → no disparity
    assert result == 0.0