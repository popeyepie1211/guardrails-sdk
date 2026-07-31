from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class Diagnosis(str, Enum):
    NORMAL = "NORMAL"
    SYSTEMIC_DATA_DRIFT = "SYSTEMIC_DATA_DRIFT"
    ADVERSARIAL_PROBE = "ADVERSARIAL_PROBE"
    MODEL_BIAS = "MODEL_BIAS"
    PRIVACY_RISK = "PRIVACY_RISK"
    SECURITY_RISK = "SECURITY_RISK"
    TRANSPARENCY_DEGRADATION = "TRANSPARENCY_DEGRADATION"
    SDK_FAILURE = "SDK_FAILURE"
    SYSTEM_INSTABILITY = "SYSTEM_INSTABILITY"
    MODEL_PERFORMANCE_ANOMALY = "MODEL_PERFORMANCE_ANOMALY"


class Severity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GovernanceAction(str, Enum):
    NO_ACTION = "NO_ACTION"
    INVESTIGATE_DRIFT = "INVESTIGATE_DRIFT"
    RETRAIN_MODEL = "RETRAIN_MODEL"
    REVIEW_FAIRNESS = "REVIEW_FAIRNESS"
    ROLLBACK_MODEL = "ROLLBACK_MODEL"
    ISOLATE_MODEL = "ISOLATE_MODEL"
    CHECK_INFRASTRUCTURE = "CHECK_INFRASTRUCTURE"
    NOTIFY_OWNER = "NOTIFY_OWNER"
    REVIEW_DATA_PIPELINE = "REVIEW_DATA_PIPELINE"
    VALIDATE_INPUT_SOURCE = "VALIDATE_INPUT_SOURCE"
    RUN_BIAS_AUDIT = "RUN_BIAS_AUDIT"
    REVIEW_PRIVACY_RISK = "REVIEW_PRIVACY_RISK"
    SECURITY_INVESTIGATION = "SECURITY_INVESTIGATION"
    HUMAN_GOVERNANCE_REVIEW = "HUMAN_GOVERNANCE_REVIEW"
    TEMPORARILY_RESTRICT_MODEL = "TEMPORARILY_RESTRICT_MODEL"
    RETRAIN_WITH_RECENT_DATA = "RETRAIN_WITH_RECENT_DATA"
    REVIEW_EXPLAINABILITY = "REVIEW_EXPLAINABILITY"


class Urgency(str, Enum):
    NONE = "NONE"
    ROUTINE = "ROUTINE"
    WITHIN_72_HOURS = "WITHIN_72_HOURS"
    WITHIN_24_HOURS = "WITHIN_24_HOURS"
    IMMEDIATE = "IMMEDIATE"


@dataclass(frozen=True)
class EvidenceItem:
    signal: str
    status: str
    detail: str
    source: str = "Part A"
    strength: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal": self.signal,
            "status": self.status,
            "detail": self.detail,
            "source": self.source,
            "strength": round(float(self.strength), 3),
        }


@dataclass(frozen=True)
class DiagnosisResult:
    diagnosis: Diagnosis
    confidence: float
    evidence: List[EvidenceItem] = field(default_factory=list)


@dataclass(frozen=True)
class Recommendation:
    primary_action: GovernanceAction
    supporting_actions: List[GovernanceAction]
    urgency: Urgency
    owner_hint: str
    rationale: List[str]
    automation_allowed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_action": self.primary_action.value,
            "supporting_actions": [action.value for action in self.supporting_actions],
            "urgency": self.urgency.value,
            "owner_hint": self.owner_hint,
            "rationale": self.rationale,
            "automation_allowed": self.automation_allowed,
        }


@dataclass(frozen=True)
class JudgeDecision:
    diagnosis: Diagnosis
    severity: Severity
    confidence: float
    reason: List[str]
    evidence: List[EvidenceItem]
    recommended_action: GovernanceAction
    recommendation: Recommendation
    verdict: str
    domain: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diagnosis": self.diagnosis.value,
            "severity": self.severity.value,
            "confidence": round(float(self.confidence), 3),
            "reason": self.reason,
            "evidence": [item.to_dict() for item in self.evidence],
            "recommended_action": self.recommended_action.value,
            "recommendation": self.recommendation.to_dict(),
            "verdict": self.verdict,
            "domain": self.domain,
        }