
from typing import Dict, List
from guardrail_ai.core.exceptions import ThresholdConfigurationError

class ThresholdEvaluator:
    

    DOMAIN_CONFIG = {
        "healthcare": {"k": 2, "persistence": 0},
        "finance": {"k": 2.5, "persistence": 1},
        "standard": {"k": 3, "persistence": 3},
    }

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
            recent_failures = sum(
                1 for h in history[-persistence_required:] if h in ["warning", "critical"]
            )

            if recent_failures < persistence_required:
                # downgrade status to avoid alert fatigue
                if status in ["warning", "critical"]:
                    status = "normal"

        return {
            "metric": metric_name,
            "value": value,
            "mean": mean,
            "std": std,
            "status": status,
            "domain": domain,
            "k": k,
        }