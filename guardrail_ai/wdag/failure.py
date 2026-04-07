from typing import Dict, Any
from datetime import datetime


class SystemFailure:
    """
    Represents a critical system-level failure before metric computation.
    Used by WDAG to trigger immediate failure propagation.
    """

    def __init__(
        self,
        failure_type: str,
        message: str,
        stage: str,
        severity: str = "critical",
    ) -> None:

        self.failure_type = failure_type
        self.message = message
        self.stage = stage
        self.severity = severity
        self.timestamp = datetime.utcnow().isoformat()

    # -----------------------------
    # Factory: Schema Mismatch
    # -----------------------------
    @classmethod
    def schema_mismatch(
        cls,
        expected_features: int,
        received_features: int,
        stage: str = "inference",
    ) -> "SystemFailure":

        message = (
            f"Schema mismatch: expected {expected_features} features, "
            f"but received {received_features}."
        )

        return cls(
            failure_type="schema_mismatch",
            message=message,
            stage=stage,
        )

    # -----------------------------
    # Factory: Exception Capture
    # -----------------------------
    @classmethod
    def from_exception(
        cls,
        error: Exception,
        stage: str = "inference",
    ) -> "SystemFailure":

        return cls(
            failure_type="inference_crash",
            message=str(error),
            stage=stage,
        )

    # -----------------------------
    # Convert to Dict (for logging / API)
    # -----------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_type": self.failure_type,
            "message": self.message,
            "stage": self.stage,
            "severity": self.severity,
            "timestamp": self.timestamp,
        }