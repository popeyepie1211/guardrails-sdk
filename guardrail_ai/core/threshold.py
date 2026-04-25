
from typing import Dict, List
from guardrail_ai.core.exceptions import ThresholdConfigurationError
from guardrail_ai.config import DOMAIN_CONFIG

class ThresholdEvaluator:
    

    DOMAIN_CONFIG = DOMAIN_CONFIG

    @staticmethod
    def evaluate(
        metric_name: str,
        value: float,
        mean: float,
        std: float,
        direction: str,
        domain: str,
        history: List[str] = None,
    ) -> dict:

        if domain not in ThresholdEvaluator.DOMAIN_CONFIG:
            raise ThresholdConfigurationError(f"Unsupported domain: {domain}")

        config = ThresholdEvaluator.DOMAIN_CONFIG[domain]
        k = config["k"]
        persistence_required = config["persistence"]

        # -----------------------------
        # Edge Case: std = 0
        # -----------------------------
        if std == 0:
            return {
                "metric": metric_name,
                "value": value,
                "mean": mean,
                "std": std,
                "status": "normal",
                "domain": domain,
                "k": k,
            }

        # -----------------------------
        # Thresholds
        # -----------------------------
        warning_upper = mean + (k - 1) * std
        critical_upper = mean + k * std

        warning_lower = mean - (k - 1) * std
        critical_lower = mean - k * std

        status = "normal"

        # -----------------------------
        # Directional Logic
        # -----------------------------
        if direction == "upper":
            if value > critical_upper:
                status = "critical"
            elif value > warning_upper:
                status = "warning"

        elif direction == "lower":
            if value < critical_lower:
                status = "critical"
            elif value < warning_lower:
                status = "warning"

        elif direction == "two-sided":
            if value > critical_upper or value < critical_lower:
                status = "critical"
            elif value > warning_upper or value < warning_lower:
                status = "warning"

        else:
            raise ThresholdConfigurationError(f"Invalid direction: {direction}")

        # -----------------------------
        # Persistence Filter
        # -----------------------------
        if history is not None and persistence_required > 0:
           failures = sum(
            1 for h in history[-persistence_required:] if h in ["warning", "critical"]
                     )

           if status in ["warning", "critical"]:
                if value > mean + (k * 3 * std):   # extreme deviation
                    status = "critical"

                elif failures < persistence_required:
                   status = "warning"

                else:
                   status = "critical"
        return {
            "metric": metric_name,
            "value": value,
            "mean": mean,
            "std": std,
            "status": status,
            "domain": domain,
            "k": k,
        }