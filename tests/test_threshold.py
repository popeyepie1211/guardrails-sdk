import pytest

from guardrail_ai.core.threshold import ThresholdEvaluator
from guardrail_ai.core.exceptions import ThresholdConfigurationError


# -----------------------------
# Upper Direction (STANDARD domain)
# -----------------------------
def test_normal_upper():
    result = ThresholdEvaluator.evaluate(
        metric_name="psi",
        value=0.06,
        mean=0.05,
        std=0.01,
        direction="upper",
        domain="standard",
    )
    assert result["status"] == "normal"


def test_warning_upper():
    result = ThresholdEvaluator.evaluate(
        metric_name="psi",
        value=0.071,
        mean=0.05,
        std=0.01,
        direction="upper",
        domain="standard",
    )
    assert result["status"] == "warning"


def test_critical_upper():
    result = ThresholdEvaluator.evaluate(
        metric_name="psi",
        value=0.085,
        mean=0.05,
        std=0.01,
        direction="upper",
        domain="standard",
    )
    assert result["status"] == "critical"


# -----------------------------
# Lower Direction
# -----------------------------
def test_normal_lower():
    result = ThresholdEvaluator.evaluate(
        metric_name="linf",
        value=0.82,
        mean=0.80,
        std=0.05,
        direction="lower",
        domain="standard",
    )
    assert result["status"] == "normal"


def test_warning_lower():
    result = ThresholdEvaluator.evaluate(
        metric_name="linf",
        value=0.69,
        mean=0.80,
        std=0.05,
        direction="lower",
        domain="standard",
    )
    assert result["status"] == "warning"


def test_critical_lower():
    result = ThresholdEvaluator.evaluate(
        metric_name="linf",
        value=0.60,
        mean=0.80,
        std=0.05,
        direction="lower",
        domain="standard",
    )
    assert result["status"] == "critical"


# -----------------------------
# Two-Sided
# -----------------------------
def test_two_sided():
    result = ThresholdEvaluator.evaluate(
        metric_name="psi",
        value=0.09,
        mean=0.05,
        std=0.01,
        direction="two-sided",
        domain="standard",
    )
    assert result["status"] in ["warning", "critical"]


# -----------------------------
# Domain Sensitivity
# -----------------------------
def test_healthcare_stricter():
    result = ThresholdEvaluator.evaluate(
        metric_name="psi",
        value=0.071,
        mean=0.05,
        std=0.01,
        direction="upper",
        domain="healthcare",
    )
    assert result["status"] in ["warning", "critical"]


# -----------------------------
# Zero Std
# -----------------------------
def test_zero_std():
    result = ThresholdEvaluator.evaluate(
        metric_name="psi",
        value=0.06,
        mean=0.05,
        std=0.0,
        direction="upper",
        domain="standard",
    )
    assert result["status"] == "normal"


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
            direction="sideways",
            domain="standard",
        )


# -----------------------------
# Invalid Domain
# -----------------------------
def test_invalid_domain():
    with pytest.raises(ThresholdConfigurationError):
        ThresholdEvaluator.evaluate(
            metric_name="psi",
            value=0.06,
            mean=0.05,
            std=0.01,
            direction="upper",
            domain="unknown",
        )