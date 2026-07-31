from typing import Any, Dict, List, Optional, Tuple

from guardrail_ai.digital_judge.models import (
    Diagnosis,
    DiagnosisResult,
    EvidenceItem,
    GovernanceAction,
    JudgeDecision,
    Recommendation,
    Severity,
    Urgency,
)



STATUS_WEIGHT = {
    "green": 0.0,
    "normal": 0.0,
    "healthy": 0.0,
    "info": 0.1,
    "no_baseline": 0.25,
    "warning": 0.65,
    "critical": 1.0,
}

DOMAIN_SEVERITY_BUMP = {
    "healthcare": 1,
    "finance": 1,
    "standard": 0,
    "retail": 0,
}

SEVERITY_ORDER = [
    Severity.INFO,
    Severity.LOW,
    Severity.MEDIUM,
    Severity.HIGH,
    Severity.CRITICAL,
]


class DigitalJudge:
    """
    Post-monitoring governance reasoning layer.

    The Digital Judge never computes metrics.
    It consumes Part A outputs and converts them into diagnosis,
    severity, evidence, verdict, and recommended governance action.
    """

    def judge(self, governance_result: Dict[str, Any]) -> Dict[str, Any]:
        decision = self.decide(governance_result)
        return decision.to_dict()

    def decide(self, governance_result: Dict[str, Any]) -> JudgeDecision:
        domain = str(governance_result.get("domain", "standard")).lower()

        metric_status = self._extract_metric_status(governance_result)
        wdag_status = governance_result.get("wdag_status", {}) or {}

        diagnosis_result = self._diagnose(metric_status, wdag_status)
        severity = self._assess_severity(
            diagnosis=diagnosis_result.diagnosis,
            confidence=diagnosis_result.confidence,
            domain=domain,
            evidence=diagnosis_result.evidence,
        )

        reasons = [item.detail for item in diagnosis_result.evidence]
        recommendation = self._recommend(
            diagnosis=diagnosis_result.diagnosis,
            severity=severity,
            domain=domain,
            reasons=reasons,
        )
        verdict = self._generate_verdict(
            model_id=governance_result.get("model_id"),
            diagnosis=diagnosis_result.diagnosis,
            severity=severity,
            confidence=diagnosis_result.confidence,
            reasons=reasons,
            recommendation=recommendation,
            domain=domain,
        )

        return JudgeDecision(
            diagnosis=diagnosis_result.diagnosis,
            severity=severity,
            confidence=diagnosis_result.confidence,
            reason=reasons,
            evidence=diagnosis_result.evidence,
            recommended_action=recommendation.primary_action,
            recommendation=recommendation,
            verdict=verdict,
            domain=domain,
        )

    def _diagnose(
        self,
        metric_status: Dict[str, str],
        wdag_status: Dict[str, Any],
    ) -> DiagnosisResult:
        psi = self._signal_weight(metric_status, "psi")
        ood = self._signal_weight(metric_status, "ood_score")
        linf = self._signal_weight(metric_status, "linf")
        fairness = max(
            self._signal_weight(metric_status, "fairness"),
            self._signal_weight(metric_status, "statistical_parity"),
        )
        privacy = self._signal_weight(metric_status, "privacy_score")
        shap = max(
            self._signal_weight(metric_status, "transparency"),
            self._signal_weight(metric_status, "shap_importance"),
        )
        gini = self._signal_weight(metric_status, "gini")

        heartbeat_lost = self._heartbeat_lost(wdag_status)
        critical_nodes = self._count_wdag_nodes(wdag_status, {"critical"})
        warning_nodes = self._count_wdag_nodes(wdag_status, {"warning"})

        candidates: List[DiagnosisResult] = []

        if heartbeat_lost:
            candidates.append(DiagnosisResult(
                diagnosis=Diagnosis.SDK_FAILURE,
                confidence=0.96,
                evidence=[
                    EvidenceItem(
                        signal="heartbeat",
                        status="critical",
                        detail="Heartbeat monitoring indicates a lost or inactive SDK/node.",
                        source="WDAG",
                        strength=1.0,
                    )
                ],
            ))

        if critical_nodes >= 2:
            candidates.append(DiagnosisResult(
                diagnosis=Diagnosis.SYSTEM_INSTABILITY,
                confidence=min(0.98, 0.75 + critical_nodes * 0.08),
                evidence=[
                    EvidenceItem(
                        signal="wdag_status",
                        status="critical",
                        detail=f"{critical_nodes} WDAG nodes are critical, indicating system-level instability.",
                        source="WDAG",
                        strength=1.0,
                    )
                ],
            ))

        if psi >= 0.65 and ood >= 0.65:
            candidates.append(DiagnosisResult(
                diagnosis=Diagnosis.SYSTEMIC_DATA_DRIFT,
                confidence=self._confidence([psi, ood]),
                evidence=[
                    self._metric_evidence("psi", metric_status),
                    self._metric_evidence("ood_score", metric_status),
                ],
            ))

        if ood >= 0.65 and psi < 0.65:
            candidates.append(DiagnosisResult(
                diagnosis=Diagnosis.ADVERSARIAL_PROBE,
                confidence=self._confidence([ood, max(0.35, 1 - psi)]),
                evidence=[
                    self._metric_evidence("ood_score", metric_status),
                    EvidenceItem(
                        signal="psi",
                        status=metric_status.get("psi", "normal"),
                        detail="OOD is elevated while PSI is not elevated, suggesting unusual probes rather than broad drift.",
                        source="VitalsEngine",
                        strength=max(0.35, 1 - psi),
                    ),
                ],
            ))

        if fairness >= 0.65 and psi < 0.65:
            candidates.append(DiagnosisResult(
                diagnosis=Diagnosis.MODEL_BIAS,
                confidence=self._confidence([fairness, max(0.35, 1 - psi)]),
                evidence=[
                    self._metric_evidence("statistical_parity", metric_status),
                    EvidenceItem(
                        signal="psi",
                        status=metric_status.get("psi", "normal"),
                        detail="Fairness is degraded while population drift is not the dominant signal.",
                        source="VitalsEngine",
                        strength=max(0.35, 1 - psi),
                    ),
                ],
            ))

        if privacy >= 0.65:
            candidates.append(DiagnosisResult(
                diagnosis=Diagnosis.PRIVACY_RISK,
                confidence=self._confidence([privacy]),
                evidence=[self._metric_evidence("privacy_score", metric_status)],
            ))

        if linf >= 0.65:
            candidates.append(DiagnosisResult(
                diagnosis=Diagnosis.SECURITY_RISK,
                confidence=self._confidence([linf]),
                evidence=[self._metric_evidence("linf", metric_status)],
            ))

        if shap >= 0.65:
            candidates.append(DiagnosisResult(
                diagnosis=Diagnosis.TRANSPARENCY_DEGRADATION,
                confidence=self._confidence([shap]),
                evidence=[self._metric_evidence("shap_importance", metric_status)],
            ))

        if gini >= 0.65:
            candidates.append(DiagnosisResult(
                diagnosis=Diagnosis.MODEL_PERFORMANCE_ANOMALY,
                confidence=self._confidence([gini]),
                evidence=[self._metric_evidence("gini", metric_status)],
            ))

        if not candidates:
            evidence = []
            if warning_nodes:
                evidence.append(EvidenceItem(
                    signal="wdag_status",
                    status="warning",
                    detail=f"{warning_nodes} WDAG nodes are warning but no dominant diagnosis was identified.",
                    source="WDAG",
                    strength=0.5,
                ))
            else:
                evidence.append(EvidenceItem(
                    signal="overall",
                    status="normal",
                    detail="No critical governance pattern was detected from Part A outputs.",
                    source="DigitalJudge",
                    strength=1.0,
                ))

            return DiagnosisResult(
                diagnosis=Diagnosis.NORMAL,
                confidence=0.9,
                evidence=evidence,
            )

        return max(candidates, key=lambda item: item.confidence)

    def _assess_severity(
        self,
        diagnosis: Diagnosis,
        confidence: float,
        domain: str,
        evidence: List[EvidenceItem],
    ) -> Severity:
        base = {
            Diagnosis.NORMAL: Severity.INFO,
            Diagnosis.SYSTEMIC_DATA_DRIFT: Severity.HIGH,
            Diagnosis.ADVERSARIAL_PROBE: Severity.HIGH,
            Diagnosis.MODEL_BIAS: Severity.HIGH,
            Diagnosis.PRIVACY_RISK: Severity.HIGH,
            Diagnosis.SECURITY_RISK: Severity.HIGH,
            Diagnosis.TRANSPARENCY_DEGRADATION: Severity.MEDIUM,
            Diagnosis.SDK_FAILURE: Severity.CRITICAL,
            Diagnosis.SYSTEM_INSTABILITY: Severity.CRITICAL,
            Diagnosis.MODEL_PERFORMANCE_ANOMALY: Severity.MEDIUM,
        }[diagnosis]

        index = SEVERITY_ORDER.index(base)

        if confidence < 0.7 and index > 1:
            index -= 1

        if any(item.status == "critical" for item in evidence):
            index = max(index, SEVERITY_ORDER.index(Severity.HIGH))

        index += DOMAIN_SEVERITY_BUMP.get(domain, 0)
        index = min(index, len(SEVERITY_ORDER) - 1)

        return SEVERITY_ORDER[index]

    def _recommend(
        self,
        diagnosis: Diagnosis,
        severity: Severity,
        domain: str,
        reasons: List[str],
    ) -> Recommendation:
        owner_hint = {
            Diagnosis.SYSTEMIC_DATA_DRIFT: "Data Governance / ML Operations Team",
            Diagnosis.ADVERSARIAL_PROBE: "Security / ML Operations Team",
            Diagnosis.MODEL_BIAS: "Responsible AI / Fairness Review Team",
            Diagnosis.PRIVACY_RISK: "Privacy / Compliance Team",
            Diagnosis.SECURITY_RISK: "Security / ML Operations Team",
            Diagnosis.TRANSPARENCY_DEGRADATION: "Model Explainability Review Team",
            Diagnosis.SDK_FAILURE: "Platform / SDK Operations Team",
            Diagnosis.SYSTEM_INSTABILITY: "ML Platform Incident Team",
            Diagnosis.MODEL_PERFORMANCE_ANOMALY: "Model Owner / ML Operations Team",
            Diagnosis.NORMAL: "Model Owner",
        }[diagnosis]

        action_map: Dict[Diagnosis, Tuple[GovernanceAction, List[GovernanceAction]]] = {
            Diagnosis.NORMAL: (
                GovernanceAction.NO_ACTION,
                [],
            ),
            Diagnosis.SYSTEMIC_DATA_DRIFT: (
                GovernanceAction.INVESTIGATE_DRIFT,
                [
                    GovernanceAction.REVIEW_DATA_PIPELINE,
                    GovernanceAction.VALIDATE_INPUT_SOURCE,
                    GovernanceAction.RETRAIN_WITH_RECENT_DATA,
                    GovernanceAction.NOTIFY_OWNER,
                ],
            ),
            Diagnosis.ADVERSARIAL_PROBE: (
                GovernanceAction.SECURITY_INVESTIGATION,
                [
                    GovernanceAction.VALIDATE_INPUT_SOURCE,
                    GovernanceAction.TEMPORARILY_RESTRICT_MODEL,
                    GovernanceAction.NOTIFY_OWNER,
                ],
            ),
            Diagnosis.MODEL_BIAS: (
                GovernanceAction.REVIEW_FAIRNESS,
                [
                    GovernanceAction.RUN_BIAS_AUDIT,
                    GovernanceAction.HUMAN_GOVERNANCE_REVIEW,
                    GovernanceAction.RETRAIN_MODEL,
                    GovernanceAction.NOTIFY_OWNER,
                ],
            ),
            Diagnosis.PRIVACY_RISK: (
                GovernanceAction.REVIEW_PRIVACY_RISK,
                [
                    GovernanceAction.HUMAN_GOVERNANCE_REVIEW,
                    GovernanceAction.TEMPORARILY_RESTRICT_MODEL,
                    GovernanceAction.NOTIFY_OWNER,
                ],
            ),
            Diagnosis.SECURITY_RISK: (
                GovernanceAction.SECURITY_INVESTIGATION,
                [
                    GovernanceAction.ISOLATE_MODEL,
                    GovernanceAction.VALIDATE_INPUT_SOURCE,
                    GovernanceAction.NOTIFY_OWNER,
                ],
            ),
            Diagnosis.TRANSPARENCY_DEGRADATION: (
                GovernanceAction.REVIEW_EXPLAINABILITY,
                [
                    GovernanceAction.HUMAN_GOVERNANCE_REVIEW,
                    GovernanceAction.NOTIFY_OWNER,
                ],
            ),
            Diagnosis.SDK_FAILURE: (
                GovernanceAction.CHECK_INFRASTRUCTURE,
                [
                    GovernanceAction.NOTIFY_OWNER,
                    GovernanceAction.HUMAN_GOVERNANCE_REVIEW,
                ],
            ),
            Diagnosis.SYSTEM_INSTABILITY: (
                GovernanceAction.ISOLATE_MODEL,
                [
                    GovernanceAction.CHECK_INFRASTRUCTURE,
                    GovernanceAction.ROLLBACK_MODEL,
                    GovernanceAction.NOTIFY_OWNER,
                ],
            ),
            Diagnosis.MODEL_PERFORMANCE_ANOMALY: (
                GovernanceAction.HUMAN_GOVERNANCE_REVIEW,
                [
                    GovernanceAction.RETRAIN_MODEL,
                    GovernanceAction.NOTIFY_OWNER,
                ],
            ),
        }

        primary, supporting = action_map[diagnosis]
        urgency = self._urgency_for(severity)

        if domain in {"healthcare", "finance"} and primary != GovernanceAction.NO_ACTION:
            if GovernanceAction.HUMAN_GOVERNANCE_REVIEW not in supporting:
                supporting.append(GovernanceAction.HUMAN_GOVERNANCE_REVIEW)

        return Recommendation(
            primary_action=primary,
            supporting_actions=supporting,
            urgency=urgency,
            owner_hint=owner_hint,
            rationale=reasons,
            automation_allowed=False,
        )
    def _urgency_for(self, severity: Severity) -> Urgency:
        if severity == Severity.CRITICAL:
            return Urgency.IMMEDIATE

        if severity == Severity.HIGH:
            return Urgency.WITHIN_24_HOURS

        if severity == Severity.MEDIUM:
            return Urgency.WITHIN_72_HOURS

        if severity == Severity.LOW:
            return Urgency.ROUTINE

        return Urgency.NONE

    def _generate_verdict(
        self,
        model_id: Optional[str],
        diagnosis: Diagnosis,
        severity: Severity,
        confidence: float,
        reasons: List[str],
        recommendation: Recommendation,
        domain: str,
    ) -> str:
        model_name = model_id or "The monitored model"
        diagnosis_text = diagnosis.value.replace("_", " ").title()
        action_text = recommendation.primary_action.value.replace("_", " ").lower()

        if diagnosis == Diagnosis.NORMAL:
            return (
                f"The Digital Judge determined that {model_name} is operating within expected "
                "governance limits. No immediate governance intervention is recommended."
            )

        explanation = {
            Diagnosis.SYSTEMIC_DATA_DRIFT:
                "Elevated Population Stability Index and Out-of-Distribution signals indicate significant deviation between production and baseline data distributions.",
            Diagnosis.ADVERSARIAL_PROBE:
                "Out-of-distribution behavior without broad population drift suggests abnormal or potentially adversarial input activity.",
            Diagnosis.MODEL_BIAS:
                "Fairness-related threshold violations indicate potential disparity across protected or sensitive groups.",
            Diagnosis.PRIVACY_RISK:
                "Privacy-related threshold violations indicate elevated governance risk around data exposure or identifiability.",
            Diagnosis.SECURITY_RISK:
                "Security-related threshold violations indicate abnormal model robustness or input integrity risk.",
            Diagnosis.SDK_FAILURE:
                "Heartbeat monitoring indicates telemetry loss or inactive monitoring components.",
            Diagnosis.SYSTEM_INSTABILITY:
                "Multiple WDAG components are degraded, indicating possible cascading system instability.",
        }.get(
            diagnosis,
            "The monitoring output indicates a governance-relevant anomaly requiring review.",
        )

        return (
            f"The Digital Judge determined that {model_name} is experiencing {diagnosis_text} "
            f"with {severity.value.title()} severity in the {domain} domain. "
            f"{explanation} Confidence is {confidence:.2f}. "
            f"Recommended governance action: {action_text}."
        )

    def _extract_metric_status(self, governance_result: Dict[str, Any]) -> Dict[str, str]:
        metric_status: Dict[str, str] = {}

        for source_key in ("threshold_results", "metrics"):
            source = governance_result.get(source_key, {}) or {}
            for metric_name, value in source.items():
                status = self._status_from_value(value)
                if status is not None:
                    metric_status[metric_name] = status

        return metric_status

    def _status_from_value(self, value: Any) -> Optional[str]:
        if isinstance(value, dict):
            status = value.get("status")
            if isinstance(status, str):
                return status.lower()

        if isinstance(value, str):
            lowered = value.lower()
            if lowered in STATUS_WEIGHT:
                return lowered

        return None

    def _signal_weight(self, metric_status: Dict[str, str], metric_name: str) -> float:
        return STATUS_WEIGHT.get(metric_status.get(metric_name, "normal"), 0.0)

    def _metric_evidence(self, metric_name: str, metric_status: Dict[str, str]) -> EvidenceItem:
        status = metric_status.get(metric_name, "normal")
        readable = metric_name.replace("_", " ").upper()
        return EvidenceItem(
            signal=metric_name,
            status=status,
            detail=f"{readable} status is {status}.",
            source="VitalsEngine",
            strength=self._signal_weight(metric_status, metric_name),
        )

    def _confidence(self, weights: List[float]) -> float:
        if not weights:
            return 0.5

        average = sum(weights) / len(weights)
        strongest = max(weights)
        confidence = 0.55 + (average * 0.3) + (strongest * 0.15)
        return round(min(confidence, 0.99), 3)

    def _heartbeat_lost(self, wdag_status: Dict[str, Any]) -> bool:
        heartbeat = wdag_status.get("heartbeat") or wdag_status.get("heartbeat_status")
        if isinstance(heartbeat, str):
            return heartbeat.lower() in {"lost", "missing", "critical", "inactive", "timeout"}

        dead_nodes = (
            wdag_status.get("dead_nodes")
            or wdag_status.get("zombie_nodes")
            or wdag_status.get("inactive_nodes")
        )
        return isinstance(dead_nodes, list) and len(dead_nodes) > 0

    def _count_wdag_nodes(self, wdag_status: Dict[str, Any], statuses: set) -> int:
        nodes = wdag_status.get("nodes", wdag_status)

        if not isinstance(nodes, dict):
            return 0

        count = 0
        for node_data in nodes.values():
            if isinstance(node_data, dict):
                status = str(node_data.get("status", "")).lower()
            else:
                status = str(node_data).lower()

            if status in statuses:
                count += 1

        return count