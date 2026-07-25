```markdown
# Guardrail AI - Team Task README

This README explains what each teammate needs to do to integrate their part with the Guardrail AI monitoring and Digital Judge system.

The core Python governance engine is already implemented.

Your job is to connect the engine output to database, API, dashboard, and integrations.

---

## Current Core Pipeline

The completed core pipeline is:

```text
SDK
    ↓
Redis Queue
    ↓
Worker Auditor
    ↓
Validator
    ↓
VitalsEngine
    ↓
Threshold Evaluator
    ↓
WDAG
    ↓
Digital Judge
    ↓
Governance Decision / Report
```

After this point, teammates handle:

```text
TimescaleDB
    ↓
FastAPI
    ↓
React Dashboard
    ↓
Slack / Jira / Webhooks / Deployment Actions
```

---

## Most Important Rule

Do **not** recompute metrics outside the core engine.

- `VitalsEngine` computes metrics.
- `ThresholdEvaluator` evaluates metric status.
- `WDAG` propagates status.
- `DigitalJudge` creates diagnosis, severity, verdict, and recommended action.

Database, API, dashboard, and integrations should only consume the final JSON output.

---

## Output You Will Receive

After every monitored batch, the core system can produce:

```python
decision = DigitalJudge().judge(governance_result)
report = GovernanceReportBuilder().build(decision, governance_result)
```

The `decision` contains:

- Diagnosis
- Severity
- Confidence
- Reason
- Recommended action
- Verdict

The `report` contains:

- Report ID
- Governance health
- Metric evidence
- Affected WDAG components
- Governance impact
- Recommended action plan
- Full audit-ready report data

Store and display these outputs directly.

---

## Task 1: Database / TimescaleDB Team

Your task is to store monitoring and governance outputs.

Recommended fields:

```text
time
model_id
domain
environment
part_a_status
metrics_json
wdag_status_json
digital_judge_decision_json
governance_report_json
diagnosis
severity
confidence
recommended_action
governance_health
```

Store these as JSON where possible:

```text
metrics_json
wdag_status_json
digital_judge_decision_json
governance_report_json
```

Do not flatten all details too early because the report needs auditability.

---

## Task 2: FastAPI Team

Your task is to expose the stored governance data through API endpoints.

Suggested endpoints:

```text
GET /api/vitals/latest?model_id=...
GET /api/vitals/history?model_id=...
GET /api/governance/latest?model_id=...
GET /api/governance/history?model_id=...
GET /api/governance/report/latest?model_id=...
```

The API should return:

- Latest metrics
- Latest WDAG status
- Latest Digital Judge decision
- Latest governance report
- Historical reports

Important dashboard fields:

```text
governance_health
diagnosis
severity
confidence
recommended_action
verdict
metric_evidence
affected_components
wdag_contribution
governance_impact
```

---

## Task 3: React Dashboard Team

Your task is to visualize the API output.

Suggested dashboard sections:

```text
1. Governance Health
2. Diagnosis Summary
3. Severity and Confidence
4. Metric Evidence Table
5. WDAG Graph
6. Affected Components
7. Governance Impact
8. Recommended Action
9. Report History
```

Do not calculate diagnosis or severity in the frontend.

The dashboard should only display values returned by the API.

---

## Task 4: Redis / Worker Integration Team

Your task is to connect SDK batches to the core engine.

Worker flow:

```python
part_a_result = executor.run(node_name, batch_df)

governance_result = {
    "model_id": model_id,
    "domain": domain,
    "environment": "Production",
    "threshold_results": part_a_result.get("metrics", {}),
    "metrics": part_a_result.get("metrics", {}),
    "wdag_status": {
        "nodes": graph.to_dict()
    }
}

decision = DigitalJudge().judge(governance_result)
report = GovernanceReportBuilder().build(decision, governance_result)
```

Then send/store:

```text
part_a_result
governance_result
decision
report
```

---

## Task 5: SDK Team

Your task is to send enough production inference data for monitoring.

Each event should include:

```json
{
  "eventId": "...",
  "modelId": "...",
  "timestamp": "...",
  "latencyMs": 123.45,
  "inputFeatures": {
    "feature_1": 10,
    "feature_2": 0.42
  },
  "prediction": {
    "value": 0.87,
    "label": "approved",
    "confidence": 0.91,
    "type": "binary"
  },
  "metadata": {
    "domain": "finance",
    "prediction_type": "binary",
    "node_name": "SDK_Intercept",
    "model_version": "v1"
  }
}
```

Required:

- Stable `modelId`
- Complete input features
- Numeric prediction value when possible
- Domain metadata
- Model version if available

---

## Task 6: Integrations Team

Your task is to map recommended actions to external tools.

Example mappings:

```text
INVESTIGATE_DRIFT     → Jira investigation ticket
REVIEW_FAIRNESS       → Responsible AI review
CHECK_INFRASTRUCTURE  → Platform alert
ISOLATE_MODEL         → Manual isolation workflow
RETRAIN_MODEL         → Retraining workflow
NOTIFY_OWNER          → Slack/PagerDuty notification
```

Important:

The Digital Judge only recommends actions.

It must not directly:

- create Jira tickets
- send Slack alerts
- trigger PagerDuty
- rollback models
- kill deployments
- retrain models

Any real action should happen in your integration module, preferably with human approval.

---

## Minimal Integration Contract

Everyone should follow this contract:

```python
governance_result = {
    "model_id": model_id,
    "domain": domain,
    "environment": environment,
    "threshold_results": part_a_result.get("metrics", {}),
    "metrics": part_a_result.get("metrics", {}),
    "wdag_status": {
        "nodes": graph.to_dict()
    }
}
```

Then:

```python
decision = DigitalJudge().judge(governance_result)
report = GovernanceReportBuilder().build(decision, governance_result)
```

These are the source-of-truth outputs:

```text
decision
report
```

---

## Do Not Change

Please do not change these core design decisions:

- Do not compute metrics in the dashboard.
- Do not compute metrics in the API.
- Do not compute metrics in the database layer.
- Do not make WDAG compute metrics.
- Do not make Digital Judge compute metrics.
- Do not make Digital Judge call external services.
- Do not execute kill-switch or rollback actions inside Digital Judge.

The core engine produces governance decisions. Other modules consume, store, display, or act on those decisions.

---

## How to Test

Run all tests:

```cmd
venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Run real-time Part A + Part B simulation:

```cmd
venv\Scripts\python.exe run_realtime_part_a_b.py
```

Expected output:

```text
Batch 1: Part A=...
Diagnosis=...
Severity=...
Action=...

FINAL GOVERNANCE REPORT
...
```

---

## Final Summary

The Python core is the governance brain.

Teammates should build the surrounding system:

- Database stores outputs.
- API exposes outputs.
- Dashboard visualizes outputs.
- Integrations map recommendations to actions.

Do not duplicate or redesign the governance logic.
```