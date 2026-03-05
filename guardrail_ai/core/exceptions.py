"""
core/exceptions.py

Custom exception classes for Guardrail AI Monitoring Engine.
These provide structured error handling across the system.
"""


class GuardrailException(Exception):
    """
    Base exception for all Guardrail AI errors.
    All custom exceptions should inherit from this.
    """

    def __init__(self, message: str):
        super().__init__(message)


class BaselineValidationError(GuardrailException):
    """
    Raised when baseline_summary structure is invalid
    or missing required metrics.
    """
    pass


class InputValidationError(GuardrailException):
    """
    Raised when incoming telemetry batch (DataFrame)
    fails schema validation.
    """
    pass


class ThresholdConfigurationError(GuardrailException):
    """
    Raised when threshold configuration is invalid
    or incompatible with baseline statistics.
    """
    pass


class MetricComputationError(GuardrailException):
    """
    Raised when a metric computation fails due to
    numerical instability or invalid input.
    """
    pass