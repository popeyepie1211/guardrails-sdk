from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, Optional, Union
from uuid import uuid4

from guardrail_ai.digital_judge.models import JudgeDecision


METRIC_LABELS = {
    "psi": "Population Stability Index (PSI)",
    "ood_score": "Out-of-Distribution Score",
    "linf": "L-infinity Security Score",
    "gini": "Gini Coefficient",
    "statistical_parity": "Statistical Parity",
    "privacy_score": "Privacy Score",
    "shap_importance": "SHAP Transparency",
    "transparency": "Transparency",
}

METRIC_CATEGORIES = {
    "psi": "Drift",
    "ood_score": "Security",
    "linf": "Security",
    "gini": "Fairness",
    "statistical_parity": "Fairness",
    "privacy_score": "Privacy",
    "shap_importance": "Transparency",
    "transparency": "Transparency",
}

METRIC_DIRECTIONS = {
    "statistical_parity": "upper",
    "gini": "upper",
    "psi": "upper",
    "linf": "lower",
    "ood_score": "upper",
    "privacy_score": "upper",
    "shap_importance": "upper",
    "transparency": "upper",
}


class GovernanceReportBuilder:
    FRAMEWORK_VERSION = "Guardrail AI v1.0"
    DIGITAL_JUDGE_VERSION = "1.0"

    def build(
        self,
        decision: Union[JudgeDecision, Dict[str, Any]],
        governance_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        started_at = perf_counter()
        decision_dict = self._to_dict(decision)
        governance_result = governance_result or {}
        generated_at = datetime.now(timezone.utc)

        metric_evidence = self._metric_evidence(governance_result)
        affected_components = self._affected_components(governance_result)
        wdag_contribution = self._wdag_contribution(governance_result, affected_components)

        report = {
            "report_type": "GUARDRAIL_AI_DIGITAL_JUDGE_REPORT",
            "report_id": self._report_id(generated_at),
            "generated_at": generated_at.isoformat(),
            "framework_version": self.FRAMEWORK_VERSION,
            "digital_judge_version": self.DIGITAL_JUDGE_VERSION,
            "environment": governance_result.get("environment", "Production"),
            "model_id": governance_result.get("model_id", "UNKNOWN_MODEL"),
            "domain": decision_dict.get("domain", governance_result.get("domain", "standard")),
            "governance_health": self._governance_health(decision_dict),
            "executive_summary": self._executive_summary(decision_dict),
            "diagnosis": {
                "label": decision_dict["diagnosis"],
                "severity": decision_dict["severity"],
                "confidence": decision_dict["confidence"],
                "verdict": decision_dict["verdict"],
            },
            "metric_evidence_note": (
                "Normal metrics are included to provide complete governance context "
                "and show which monitored dimensions remain stable."
            ),
            "metric_evidence": metric_evidence,
            "metric_evidence_by_category": self._group_metric_evidence(metric_evidence),
            "affected_components": affected_components,
            "wdag_contribution": wdag_contribution,
            "governance_impact": self._governance_impact(decision_dict["diagnosis"]),
            "reasoning": decision_dict.get("reason", []),
            "recommended_governance_action": {
                "primary_action": decision_dict["recommended_action"],
                "action_plan": decision_dict["recommendation"],
            },
            "part_a_snapshot": self._part_a_snapshot(metric_evidence, affected_components),
            "decision": decision_dict,
        }

        report["execution_time_ms"] = round((perf_counter() - started_at) * 1000, 3)
        return report

    def render_text(self, report: Dict[str, Any]) -> str:
        diagnosis = report["diagnosis"]
        action_plan = report["recommended_governance_action"]["action_plan"]

        lines = [
            "Guardrail AI Digital Judge Report",
            "",
            "Report Metadata",
            f"- Report ID: {report['report_id']}",
            f"- Generated At: {report['generated_at']}",
            f"- Framework Version: {report['framework_version']}",
            f"- Digital Judge Version: {report['digital_judge_version']}",
            f"- Environment: {report['environment']}",
            f"- Execution Time: {report['execution_time_ms']} ms",
            "",
            f"Model ID: {report['model_id']}",
            f"Domain: {report['domain']}",
            "",
            "Overall Governance Status",
            f"- Governance Health: {report['governance_health']}",
            "",
            "Executive Summary",
            report["executive_summary"],
            "",
            "Diagnosis",
            f"- Diagnosis: {diagnosis['label']}",
            f"- Severity: {diagnosis['severity']}",
            f"- Confidence: {diagnosis['confidence']}",
            "",
            "Verdict",
            diagnosis["verdict"],
            "",
            "Metric Evidence",
            report["metric_evidence_note"],
        ]

        grouped = report.get("metric_evidence_by_category", {})
        if grouped:
            for category, items in grouped.items():
                lines.extend(["", category])
                for item in items:
                    lines.extend([
                        f"- {item['label']}",
                        f"  Value: {item['value']}",
                        f"  Threshold: {item['threshold']}",
                        f"  Status: {item['status']}",
                    ])
        else:
            lines.append("- No metric evidence available.")

        lines.extend(["", "Affected Components"])
        affected = report.get("affected_components", [])
        if affected:
            for item in affected:
                lines.append(f"- {item['name']} ({item['status']}) - Owner: {item['owner']}")
        else:
            lines.append("- No affected WDAG components detected.")

        lines.extend(["", "WDAG Contribution"])
        wdag = report.get("wdag_contribution", {})
        lines.append(f"- Summary: {wdag.get('summary', 'WDAG contribution unavailable.')}")
        for edge in wdag.get("propagation_edges", []):
            lines.append(f"- Propagation Edge: {edge['source']} -> {edge['target']}")

        lines.extend(["", "Potential Governance Impact"])
        for impact in report.get("governance_impact", []):
            lines.append(f"- {impact}")

        lines.extend([
            "",
            "Recommended Governance Action",
            f"- Primary Action: {action_plan['primary_action']}",
            f"- Urgency: {action_plan['urgency']}",
            f"- Owner Hint: {action_plan['owner_hint']}",
            f"- Automation Allowed: {action_plan['automation_allowed']}",
            "",
            "Supporting Actions",
        ])

        for action in action_plan.get("supporting_actions", []) or ["None"]:
            lines.append(f"- {action}")

        lines.extend(["", "Rationale"])
        for reason in action_plan.get("rationale", []) or ["No additional rationale provided."]:
            lines.append(f"- {reason}")

        return "\n".join(lines)

    def _to_dict(self, decision):
        if isinstance(decision, JudgeDecision):
            return decision.to_dict()
        if isinstance(decision, dict):
            return decision
        raise TypeError("decision must be a JudgeDecision or dictionary.")

    def _report_id(self, generated_at: datetime) -> str:
        return f"DJ-{generated_at.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6].upper()}"

    def _governance_health(self, decision: Dict[str, Any]) -> str:
        severity = decision.get("severity", "INFO")

        if severity == "CRITICAL":
            return "CRITICAL"
        if severity == "HIGH":
            return "UNHEALTHY"
        if severity == "MEDIUM":
            return "DEGRADED"
        if severity == "LOW":
            return "WATCH"
        return "HEALTHY"

    def _executive_summary(self, decision: Dict[str, Any]) -> str:
        diagnosis = decision["diagnosis"].replace("_", " ").title()
        severity = decision["severity"].title()
        action = decision["recommended_action"].replace("_", " ").lower()

        if decision["diagnosis"] == "NORMAL":
            return (
                "The monitored model is within expected governance limits. "
                "No immediate intervention is recommended."
            )

        return (
            f"The Digital Judge identified {diagnosis} with {severity} severity. "
            f"The recommended governance action is to {action}."
        )

    def _metric_evidence(self, governance_result: Dict[str, Any]):
        evidence = []
        source = governance_result.get("threshold_results") or governance_result.get("metrics") or {}

        for metric_name, result in source.items():
            if not isinstance(result, dict):
                continue

            evidence.append({
                "metric": metric_name,
                "label": METRIC_LABELS.get(metric_name, metric_name.replace("_", " ").title()),
                "category": METRIC_CATEGORIES.get(metric_name, "Other"),
                "value": self._round(result.get("value")),
                "threshold": self._threshold_summary(metric_name, result),
                "status": str(result.get("status", "unknown")).upper(),
            })

        return evidence

    def _group_metric_evidence(self, metric_evidence):
        grouped = {}
        category_order = ["Drift", "Fairness", "Privacy", "Security", "Transparency", "Other"]

        for category in category_order:
            items = [item for item in metric_evidence if item["category"] == category]
            if items:
                grouped[category] = items

        return grouped

    def _threshold_summary(self, metric_name: str, result: Dict[str, Any]) -> str:
        mean = result.get("mean")
        std = result.get("std")
        k = result.get("k")

        if not all(isinstance(v, (int, float)) for v in [mean, std, k]):
            return "Threshold metadata not available"

        direction = METRIC_DIRECTIONS.get(metric_name, "upper")
        upper = mean + (k * std)
        lower = mean - (k * std)

        if direction == "upper":
            return f"> {upper:.4f} critical boundary"
        if direction == "lower":
            return f"< {lower:.4f} critical boundary"
        return f"< {lower:.4f} or > {upper:.4f} critical boundary"

    def _affected_components(self, governance_result: Dict[str, Any]):
        wdag_status = governance_result.get("wdag_status", {}) or {}
        nodes = wdag_status.get("nodes", wdag_status)
        affected = []

        if not isinstance(nodes, dict):
            return affected

        for name, node in nodes.items():
            if not isinstance(node, dict):
                continue

            status = str(node.get("status", "unknown")).lower()
            if status in {"warning", "critical", "locked", "grey"}:
                affected.append({
                    "name": name,
                    "status": status.upper(),
                    "owner": node.get("owner", "Unknown"),
                    "upstream": node.get("upstream", []),
                    "downstream": node.get("downstream", []),
                })

        return affected

    def _wdag_contribution(self, governance_result: Dict[str, Any], affected_components):
        wdag_status = governance_result.get("wdag_status", {}) or {}
        nodes = wdag_status.get("nodes", wdag_status)
        propagation_edges = []

        if isinstance(nodes, dict):
            affected_names = {item["name"] for item in affected_components}

            for source_name, node in nodes.items():
                if not isinstance(node, dict):
                    continue

                for target_name in node.get("downstream", []):
                    if source_name in affected_names and target_name in affected_names:
                        propagation_edges.append({
                            "source": source_name,
                            "target": target_name,
                        })

        critical_nodes = [
            item["name"]
            for item in affected_components
            if item["status"] == "CRITICAL"
        ]

        warning_nodes = [
            item["name"]
            for item in affected_components
            if item["status"] == "WARNING"
        ]

        if propagation_edges:
            summary = (
                "WDAG status propagation indicates that governance impact moved across "
                "connected pipeline components."
            )
        elif critical_nodes:
            summary = (
                "WDAG identified critical affected component(s): "
                + ", ".join(critical_nodes)
                + "."
            )
        elif warning_nodes:
            summary = (
                "WDAG identified warning-level affected component(s): "
                + ", ".join(warning_nodes)
                + "."
            )
        else:
            summary = "WDAG did not identify affected components for this decision."

        return {
            "summary": summary,
            "critical_nodes": critical_nodes,
            "warning_nodes": warning_nodes,
            "propagation_edges": propagation_edges,
        }

    def _governance_impact(self, diagnosis: str):
        impact_map = {
            "SYSTEMIC_DATA_DRIFT": [
                "Reduced prediction reliability due to production-baseline distribution mismatch.",
                "Increased risk of model degradation under unseen input patterns.",
                "Possible compliance concern in regulated domains if monitoring response is delayed.",
            ],
            "ADVERSARIAL_PROBE": [
                "Possible malicious or abnormal probing of the deployed model.",
                "Increased security risk from out-of-distribution production inputs.",
            ],
            "MODEL_BIAS": [
                "Potential unfair treatment across protected or sensitive groups.",
                "Increased risk of regulatory and ethical governance violations.",
            ],
            "PRIVACY_RISK": [
                "Potential privacy leakage or weak anonymity protection.",
                "Requires compliance review before continued broad deployment.",
            ],
            "SDK_FAILURE": [
                "Monitoring visibility may be incomplete or unavailable.",
                "Governance decisions may be delayed until telemetry is restored.",
            ],
            "SYSTEM_INSTABILITY": [
                "Multiple governance components are degraded.",
                "Immediate operational review is required to avoid cascading failures.",
            ],
        }

        return impact_map.get(
            diagnosis,
            ["No major governance impact identified beyond current monitoring status."]
        )

    def _part_a_snapshot(self, metric_evidence, affected_components) -> Dict[str, Any]:
        return {
            "metric_statuses": {
                item["metric"]: item["status"]
                for item in metric_evidence
            },
            "affected_components": affected_components,
        }

    def _round(self, value):
        if isinstance(value, (int, float)):
            return round(float(value), 4)
        return value