from guardrail_ai.digital_judge import DigitalJudge, GovernanceReportBuilder


def test_governance_report_builder_creates_report_object():
    judge = DigitalJudge()
    report_builder = GovernanceReportBuilder()

    governance_result = {
        "model_id": "FraudDetector-v2",
        "domain": "healthcare",
        "threshold_results": {
            "psi": {"value": 0.42, "status": "critical"},
            "ood_score": {"value": 0.37, "status": "critical"},
        },
        "wdag_status": {
            "nodes": {
                "Data": {"status": "critical"},
                "Model": {"status": "warning"},
            }
        },
    }

    decision = judge.judge(governance_result)
    report = report_builder.build(decision, governance_result)

    assert report["report_type"] == "GUARDRAIL_AI_DIGITAL_JUDGE_REPORT"
    assert report["model_id"] == "FraudDetector-v2"
    assert report["domain"] == "healthcare"
    assert report["diagnosis"]["label"] == "SYSTEMIC_DATA_DRIFT"
    assert report["recommended_governance_action"]["primary_action"] == "INVESTIGATE_DRIFT"
    assert "executive_summary" in report
    assert "part_a_snapshot" in report


def test_governance_report_builder_renders_text_report():
    judge = DigitalJudge()
    report_builder = GovernanceReportBuilder()

    governance_result = {
        "model_id": "CreditApproval-v3",
        "domain": "finance",
        "threshold_results": {
            "psi": {"value": 0.03, "status": "normal"},
            "statistical_parity": {"value": 0.31, "status": "critical"},
        },
        "wdag_status": {
            "nodes": {
                "Model": {"status": "critical"},
            }
        },
    }

    decision = judge.judge(governance_result)
    report = report_builder.build(decision, governance_result)
    text_report = report_builder.render_text(report)

    assert "Guardrail AI Digital Judge Report" in text_report
    assert "CreditApproval-v3" in text_report
    assert "MODEL_BIAS" in text_report
    assert "REVIEW_FAIRNESS" in text_report