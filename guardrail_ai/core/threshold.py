"""
core/threshold.py

Implements dynamic threshold evaluation using the Three-Sigma Rule.
"""

from typing import Dict

from guardrail_ai.core.exceptions import ThresholdConfigurationError


class ThresholdEvaluator:
    """
    Evaluates metric values against baseline mean and standard deviation
    using configurable sigma rules.
    """

    WARNING_SIGMA = 2
    CRITICAL_SIGMA = 3

    @staticmethod
    def evaluate(
        metric_name: str,
        value: float,
        mean: float,
        std: float,
        direction: str = "upper",
    ) -> Dict:
        """
        Evaluate a metric value against baseline.

        direction:
            - "upper": breach if value > mean + k*std
            - "lower": breach if value < mean - k*std
        """

        if direction not in ("upper", "lower"):
            raise ThresholdConfigurationError(
                f"Invalid direction '{direction}' for metric '{metric_name}'."
            )

        if std == 0:
            # If std is zero, any deviation from mean is critical
            if value != mean:
                return {
                    "metric": metric_name,
                    "value": value,
                    "status": "critical",
                    "warning_threshold": mean,
                    "critical_threshold": mean,
                }
            else:
                return {
                    "metric": metric_name,
                    "value": value,
                    "status": "normal",
                    "warning_threshold": mean,
                    "critical_threshold": mean,
                }

        warning_threshold = (
            mean + ThresholdEvaluator.WARNING_SIGMA * std
            if direction == "upper"
            else mean - ThresholdEvaluator.WARNING_SIGMA * std
        )

        critical_threshold = (
            mean + ThresholdEvaluator.CRITICAL_SIGMA * std
            if direction == "upper"
            else mean - ThresholdEvaluator.CRITICAL_SIGMA * std
        )

        status = "normal"

        if direction == "upper":
            if value > critical_threshold:
                status = "critical"
            elif value > warning_threshold:
                status = "warning"
        else:
            if value < critical_threshold:
                status = "critical"
            elif value < warning_threshold:
                status = "warning"

        return {
            "metric": metric_name,
            "value": value,
            "status": status,
            "warning_threshold": warning_threshold,
            "critical_threshold": critical_threshold,
        }