import pytest

from guardrail_ai.core.threshold import ThresholdEvaluator
from guardrail_ai.core.exceptions import ThresholdConfigurationError


# -----------------------------
# Upper Direction Tests
# -----------------------------

def test_normal_upper():
    result = ThresholdEvaluator.evaluate(
        metric_name="psi",
        value=0.06,
        mean=0.05,
        std=0.01,
        direction="upper"
    )

    assert result["status"] == "normal"


def test_warning_upper():
    result = ThresholdEvaluator.evaluate(
        metric_name="psi",
        value=0.071,  # > mean + 2*std (0.07)
        mean=0.05,
        std=0.01,
        direction="upper"
    )

    assert result["status"] == "warning"


def test_critical_upper():
    result = ThresholdEvaluator.evaluate(
        metric_name="psi",
        value=0.085,  # > mean + 3*std (0.08)
        mean=0.05,
        std=0.01,
        direction="upper"
    )

    assert result["status"] == "critical"


# -----------------------------
# Lower Direction Tests
# -----------------------------

def test_normal_lower():
    result = ThresholdEvaluator.evaluate(
        metric_name="l_inf",
        value=0.82,
        mean=0.80,
        std=0.05,
        direction="lower"
    )

    assert result["status"] == "normal"


def test_warning_lower():
    result = ThresholdEvaluator.evaluate(
        metric_name="l_inf",
        value=0.69,  # < mean - 2*std (0.70)
        mean=0.80,
        std=0.05,
        direction="lower"
    )

    assert result["status"] == "warning"


def test_critical_lower():
    result = ThresholdEvaluator.evaluate(
        metric_name="l_inf",
        value=0.60,  # < mean - 3*std (0.65)
        mean=0.80,
        std=0.05,
        direction="lower"
    )

    assert result["status"] == "critical"


# -----------------------------
# Zero Std Case
# -----------------------------

def test_zero_std_no_deviation():
    result = ThresholdEvaluator.evaluate(
        metric_name="psi",
        value=0.05,
        mean=0.05,
        std=0.0,
        direction="upper"
    )

    assert result["status"] == "normal"


def test_zero_std_with_deviation():
    result = ThresholdEvaluator.evaluate(
        metric_name="psi",
        value=0.06,
        mean=0.05,
        std=0.0,
        direction="upper"
    )

    assert result["status"] == "critical"


# -----------------------------
# Invalid Direction
# -----------------------------

def test_invalid_direction():
    with pytest.raises(ThresholdConfigurationError):
        ThresholdEvaluator.evaluate(
            metric_name="psi",
            value=0.06,
            mean=0.05,
            std=0.01,
            direction="sideways"
        )