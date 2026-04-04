import pytest
from guardrail_ai.core.exceptions import (
    GuardrailException,
    BaselineValidationError,
    InputValidationError,
    ThresholdConfigurationError,
    MetricComputationError
)


def test_baseline_validation_error():
    with pytest.raises(BaselineValidationError):
        raise BaselineValidationError("Baseline invalid")


def test_input_validation_error():
    with pytest.raises(InputValidationError):
        raise InputValidationError("Invalid input")


def test_threshold_configuration_error():
    with pytest.raises(ThresholdConfigurationError):
        raise ThresholdConfigurationError("Bad threshold config")


def test_metric_computation_error():
    with pytest.raises(MetricComputationError):
        raise MetricComputationError("Metric failed")