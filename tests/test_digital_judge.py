from guardrail_ai.digital_judge import DigitalJudge


def test_systemic_data_drift_healthcare_is_critical():
    judge = DigitalJudge()

    result = judge.judge({
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
    })

    assert result["diagnosis"] == "SYSTEMIC_DATA_DRIFT"
    assert result["severity"] == "CRITICAL"
    assert result["recommended_action"] == "INVESTIGATE_DRIFT"
    assert result["recommendation"]["primary_action"] == "INVESTIGATE_DRIFT"
    assert "REVIEW_DATA_PIPELINE" in result["recommendation"]["supporting_actions"]
    assert "HUMAN_GOVERNANCE_REVIEW" in result["recommendation"]["supporting_actions"]
    assert result["recommendation"]["automation_allowed"] is False
    assert "systemic data drift" in result["verdict"].lower()


def test_adversarial_probe_when_ood_high_but_psi_normal():
    judge = DigitalJudge()

    result = judge.judge({
        "model_id": "LoanModel-v1",
        "domain": "standard",
        "threshold_results": {
            "psi": {"value": 0.02, "status": "normal"},
            "ood_score": {"value": 0.51, "status": "critical"},
        },
        "wdag_status": {
            "nodes": {
                "Data": {"status": "warning"},
            }
        },
    })

    assert result["diagnosis"] == "ADVERSARIAL_PROBE"
    assert result["severity"] == "HIGH"
    assert result["recommended_action"] == "SECURITY_INVESTIGATION"
    assert "VALIDATE_INPUT_SOURCE" in result["recommendation"]["supporting_actions"]


def test_model_bias_when_fairness_critical_without_population_drift():
    judge = DigitalJudge()

    result = judge.judge({
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
    })

    assert result["diagnosis"] == "MODEL_BIAS"
    assert result["severity"] == "CRITICAL"
    assert result["recommended_action"] == "REVIEW_FAIRNESS"
    assert "RUN_BIAS_AUDIT" in result["recommendation"]["supporting_actions"]
    assert "HUMAN_GOVERNANCE_REVIEW" in result["recommendation"]["supporting_actions"]


def test_sdk_failure_from_dead_nodes():
    judge = DigitalJudge()

    result = judge.judge({
        "model_id": "RiskModel-v1",
        "domain": "standard",
        "threshold_results": {},
        "wdag_status": {
            "dead_nodes": ["SDK_Intercept"],
        },
    })

    assert result["diagnosis"] == "SDK_FAILURE"
    assert result["severity"] == "CRITICAL"
    assert result["recommended_action"] == "CHECK_INFRASTRUCTURE"
    assert result["recommendation"]["urgency"] == "IMMEDIATE"


def test_system_instability_from_multiple_critical_wdag_nodes():
    judge = DigitalJudge()

    result = judge.judge({
        "model_id": "DecisionPipeline-v2",
        "domain": "standard",
        "threshold_results": {},
        "wdag_status": {
            "nodes": {
                "Data": {"status": "critical"},
                "Model": {"status": "critical"},
                "Deployment": {"status": "warning"},
            }
        },
    })

    assert result["diagnosis"] == "SYSTEM_INSTABILITY"
    assert result["severity"] == "CRITICAL"
    assert result["recommended_action"] == "ISOLATE_MODEL"
    assert "ROLLBACK_MODEL" in result["recommendation"]["supporting_actions"]


def test_normal_case_recommends_no_action():
    judge = DigitalJudge()

    result = judge.judge({
        "model_id": "StableModel-v1",
        "domain": "standard",
        "threshold_results": {
            "psi": {"value": 0.01, "status": "normal"},
            "ood_score": {"value": 0.01, "status": "normal"},
            "gini": {"value": 0.22, "status": "normal"},
        },
        "wdag_status": {
            "nodes": {
                "Data": {"status": "green"},
                "Model": {"status": "green"},
            }
        },
    })

    assert result["diagnosis"] == "NORMAL"
    assert result["severity"] == "INFO"
    assert result["recommended_action"] == "NO_ACTION"
    assert result["recommendation"]["urgency"] == "NONE"