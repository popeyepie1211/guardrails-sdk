"""
Verification test script for the integrations module.

This script runs 4 verification steps:
  1. Run dispatcher against live API with a real Slack webhook (or dry-run)
  2. Mock Jira/PagerDuty HTTP calls and print the payloads
  3. Restart check — verify state persistence prevents duplicates
  4. Trace destructive action paths (ISOLATE_MODEL, ROLLBACK_MODEL)

Usage:
    .venv\\Scripts\\python.exe integrations/verify.py
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure the repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Force UTF-8 output on Windows to handle emoji in verification messages
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("verify")

# ---------------------------------------------------------------------------
# Setup env vars for testing
# ---------------------------------------------------------------------------
os.environ.setdefault("DBAPI_BASE_URL", "http://localhost:8002")
os.environ.setdefault("WATCHED_MODEL_IDS", "loan_risk_model_v1")
os.environ.setdefault("POLL_INTERVAL_SECONDS", "9999")  # won't loop

# Set dummy credentials for Jira/PagerDuty (we'll mock the HTTP calls)
os.environ.setdefault("JIRA_BASE_URL", "https://test.atlassian.net")
os.environ.setdefault("JIRA_EMAIL", "test@example.com")
os.environ.setdefault("JIRA_API_TOKEN", "fake-token")
os.environ.setdefault("JIRA_PROJECT_KEY", "GOV")
os.environ.setdefault("PAGERDUTY_ROUTING_KEY", "fake-routing-key")

# Import AFTER setting env vars
from integrations import dispatcher, jira_client, slack_client, pagerduty_client

STATE_FILE = dispatcher.STATE_FILE
SEPARATOR = "\n" + "=" * 72 + "\n"


def _make_fake_decision(
    recommended_action: str = "INVESTIGATE_DRIFT",
    model_id: str = "loan_risk_model_v1",
    time_str: str = "2099-01-01T00:00:00.000000+00:00",
) -> dict:
    """Create a fake decision record for testing."""
    return {
        "time": time_str,
        "model_id": model_id,
        "domain": "finance",
        "environment": "Production",
        "batch_id": "test-batch-001",
        "diagnosis": "SYSTEMIC_DATA_DRIFT",
        "severity": "CRITICAL",
        "confidence": 0.99,
        "recommended_action": recommended_action,
        "verdict": (
            f"Test verdict for {recommended_action}. The Digital Judge "
            f"determined that {model_id} requires attention."
        ),
        "governance_health": "CRITICAL",
        "decision_json": {
            "diagnosis": "SYSTEMIC_DATA_DRIFT",
            "severity": "CRITICAL",
            "confidence": 0.99,
            "recommended_action": recommended_action,
            "reason": ["PSI status is critical.", "OOD SCORE status is critical."],
            "evidence": [
                {
                    "signal": "psi",
                    "status": "critical",
                    "detail": "PSI status is critical.",
                    "source": "VitalsEngine",
                    "strength": 1.0,
                },
                {
                    "signal": "ood_score",
                    "status": "critical",
                    "detail": "OOD SCORE status is critical.",
                    "source": "VitalsEngine",
                    "strength": 1.0,
                },
            ],
            "verdict": f"Test verdict for {recommended_action}.",
        },
    }


# ===================================================================
# VERIFICATION 1: Dispatcher against live API + Slack
# ===================================================================
def verify_1_live_slack():
    logger.info(SEPARATOR + "VERIFICATION 1: Live API poll + Slack notification")

    slack_url = os.environ.get("SLACK_WEBHOOK_URL", "")

    # Clean any previous state so we get at least one dispatch
    if STATE_FILE.exists():
        STATE_FILE.unlink()
        logger.info("Cleared previous state file for clean test run.")

    if not slack_url:
        logger.warning(
            "SLACK_WEBHOOK_URL not set — will capture the payload that "
            "WOULD be sent instead of posting to Slack."
        )
        # Set a dummy webhook URL so the client doesn't raise ValueError
        os.environ["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/TEST/TEST/TEST"
        # Reload the module-level var
        slack_client.SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

    # Patch ALL outgoing HTTP POST calls (Slack, Jira, PagerDuty)
    # so we can capture payloads without hitting real services.
    captured_slack_payloads = []
    captured_jira_payloads = []
    captured_pd_payloads = []

    original_post = __import__("requests").post

    def mock_post_all(url, **kwargs):
        url_str = str(url)
        payload = kwargs.get("json")
        if "hooks.slack.com" in url_str:
            captured_slack_payloads.append({"url": url_str, "json": payload})
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            return mock_resp
        elif "atlassian.net" in url_str:
            captured_jira_payloads.append({"url": url_str, "json": payload})
            mock_resp = MagicMock()
            mock_resp.status_code = 201
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {
                "id": "99999", "key": "GOV-LIVE",
                "self": f"{url_str}/99999",
            }
            return mock_resp
        elif "pagerduty.com" in url_str:
            captured_pd_payloads.append({"url": url_str, "json": payload})
            mock_resp = MagicMock()
            mock_resp.status_code = 202
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {
                "status": "success", "dedup_key": "auto",
            }
            return mock_resp
        # Allow real GET calls to dbapi to pass through
        return original_post(url, **kwargs)

    with patch("integrations.slack_client.requests.post", side_effect=mock_post_all), \
         patch("integrations.jira_client.requests.post", side_effect=mock_post_all), \
         patch("integrations.pagerduty_client.requests.post", side_effect=mock_post_all):
        state = dispatcher._load_state()
        dispatcher._poll_model("loan_risk_model_v1", state)

    if captured_slack_payloads:
        logger.info(
            "Captured Slack payload (would have been sent):\n%s",
            json.dumps(captured_slack_payloads[0]["json"], indent=2),
        )
        print("\n--- RAW SLACK PAYLOAD ---")
        print(json.dumps(captured_slack_payloads[0]["json"], indent=2))
        print("--- END SLACK PAYLOAD ---\n")
    else:
        logger.info("No Slack payloads captured (action may have gone to Jira/PD only).")

    if captured_jira_payloads:
        logger.info("Also captured %d Jira payload(s) during live poll.", len(captured_jira_payloads))
    if captured_pd_payloads:
        logger.info("Also captured %d PagerDuty payload(s) during live poll.", len(captured_pd_payloads))


    return state


# ===================================================================
# VERIFICATION 2: Jira & PagerDuty payload inspection
# ===================================================================
def verify_2_mock_jira_pagerduty():
    logger.info(SEPARATOR + "VERIFICATION 2: Jira & PagerDuty payload inspection")

    decision = _make_fake_decision("INVESTIGATE_DRIFT")

    # --- Jira ---
    captured_jira = []

    def mock_jira_post(url, **kwargs):
        captured_jira.append({"url": url, "json": kwargs.get("json")})
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "id": "12345",
            "key": "GOV-1",
            "self": "https://test.atlassian.net/rest/api/3/issue/12345",
        }
        return mock_resp

    with patch("integrations.jira_client.requests.post", side_effect=mock_jira_post):
        jira_client.create_issue(
            summary=f"[CRITICAL] SYSTEMIC_DATA_DRIFT — loan_risk_model_v1",
            description="",
            issue_type="Task",
            decision=decision,
        )

    if captured_jira:
        print("\n--- JIRA PAYLOAD ---")
        print(json.dumps(captured_jira[0]["json"], indent=2))
        print(f"URL: {captured_jira[0]['url']}")
        print("--- END JIRA PAYLOAD ---\n")

    # --- PagerDuty ---
    captured_pd = []

    def mock_pd_post(url, **kwargs):
        captured_pd.append({"url": url, "json": kwargs.get("json")})
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "status": "success",
            "message": "Event processed",
            "dedup_key": "test-dedup-key",
        }
        return mock_resp

    pd_decision = _make_fake_decision("CHECK_INFRASTRUCTURE")
    with patch("integrations.pagerduty_client.requests.post", side_effect=mock_pd_post):
        pagerduty_client.trigger_alert(
            summary="[CRITICAL] SYSTEM_INSTABILITY — loan_risk_model_v1: CHECK_INFRASTRUCTURE",
            source="loan_risk_model_v1",
            severity="CRITICAL",
            dedup_key="guardrails-loan_risk_model_v1-test-batch-001",
        )

    if captured_pd:
        print("\n--- PAGERDUTY PAYLOAD ---")
        print(json.dumps(captured_pd[0]["json"], indent=2))
        print(f"URL: {captured_pd[0]['url']}")
        print("--- END PAGERDUTY PAYLOAD ---\n")


# ===================================================================
# VERIFICATION 3: Restart duplicate prevention
# ===================================================================
def verify_3_restart_no_duplicates(prev_state):
    logger.info(SEPARATOR + "VERIFICATION 3: Restart — no duplicate notifications")

    # State should have been saved by Verification 1
    if not STATE_FILE.exists():
        logger.warning("State file does not exist — cannot verify duplicate prevention.")
        return

    logger.info("State file contents BEFORE restart simulation:")
    with open(STATE_FILE, "r") as f:
        state_contents = json.load(f)
    print(json.dumps(state_contents, indent=2))

    # Simulate a "restart" by re-loading state from disk
    fresh_state = dispatcher._load_state()

    dispatch_count = 0
    original_handler = dispatcher._handle_slack

    def counting_handler(decision, *, manual=False):
        nonlocal dispatch_count
        dispatch_count += 1
        logger.info(
            "DUPLICATE CHECK: Would dispatch to Slack for batch_id=%s time=%s",
            decision.get("batch_id"), decision.get("time"),
        )

    with patch("integrations.dispatcher._handle_slack", side_effect=counting_handler):
        with patch("integrations.slack_client.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp
            dispatcher._poll_model("loan_risk_model_v1", fresh_state)

    if dispatch_count == 0:
        logger.info(
            "✅ PASS: No decisions were re-dispatched after restart. "
            "State persistence is working correctly."
        )
        print("\n✅ VERIFICATION 3 PASSED: No duplicate notifications after restart.\n")
    else:
        logger.error(
            "❌ FAIL: %d decision(s) were re-dispatched after restart!",
            dispatch_count,
        )
        print(f"\n❌ VERIFICATION 3 FAILED: {dispatch_count} duplicate(s) sent.\n")


# ===================================================================
# VERIFICATION 4: Destructive action path trace
# ===================================================================
def verify_4_destructive_action_trace():
    logger.info(SEPARATOR + "VERIFICATION 4: Destructive action path trace")

    # Ensure SLACK_WEBHOOK_URL is set so slack_client doesn't raise ValueError
    if not os.environ.get("SLACK_WEBHOOK_URL"):
        os.environ["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/TEST/TEST/TEST"
        slack_client.SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

    destructive_actions = [
        "ISOLATE_MODEL",
        "ROLLBACK_MODEL",
        "RETRAIN_MODEL",
        "TEMPORARILY_RESTRICT_MODEL",
        "RETRAIN_WITH_RECENT_DATA",
    ]

    all_passed = True

    for action in destructive_actions:
        logger.info("--- Tracing %s ---", action)

        handler = dispatcher.ACTION_MAP.get(action)
        if handler is None:
            logger.error("❌ FAIL: %s not found in ACTION_MAP!", action)
            all_passed = False
            continue

        # Verify handler identity — it should be _handle_slack_only_manual
        handler_name = handler.__name__
        logger.info("  Handler: %s", handler_name)

        if handler_name != "_handle_slack_only_manual":
            logger.error(
                "❌ FAIL: %s maps to %s instead of _handle_slack_only_manual!",
                action, handler_name,
            )
            all_passed = False
            continue

        # Now run the handler with mocks and verify ONLY slack is called.
        # Use a single unified mock for requests.post since all three client
        # modules share the same `requests` module object — patching it at
        # different module paths would just overwrite each other.
        calls = {"slack": False, "jira": False, "pagerduty": False}

        def unified_mock_post(url, **kwargs):
            url_str = str(url)
            if "hooks.slack.com" in url_str:
                calls["slack"] = True
                payload = kwargs.get("json", {})
                blocks = payload.get("blocks", [])
                has_warning = any(
                    "manual human execution" in str(block).lower()
                    for block in blocks
                )
                if has_warning:
                    logger.info("  [OK] Manual action warning present in Slack payload")
                else:
                    logger.error("  [FAIL] Manual action warning MISSING!")
            elif "atlassian.net" in url_str:
                calls["jira"] = True
            elif "pagerduty.com" in url_str:
                calls["pagerduty"] = True
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {"ok": True}
            return mock_resp

        decision = _make_fake_decision(action)

        with patch("requests.post", side_effect=unified_mock_post):
            handler(decision)

        results = []
        if calls["slack"]:
            results.append("Slack=YES")
        else:
            results.append("Slack=NO")
        if calls["jira"]:
            results.append("Jira=YES [UNSAFE!]")
            all_passed = False
        else:
            results.append("Jira=NO [OK]")
        if calls["pagerduty"]:
            results.append("PagerDuty=YES [UNSAFE!]")
            all_passed = False
        else:
            results.append("PagerDuty=NO [OK]")

        passed = calls["slack"] and not calls["jira"] and not calls["pagerduty"]
        if not passed:
            all_passed = False
        status = "[PASS]" if passed else "[FAIL]"
        logger.info("  %s: %s -> %s", status, action, ", ".join(results))
        print(f"  {status}: {action} -> {', '.join(results)}")

    if all_passed:
        print("\n[PASS] VERIFICATION 4 PASSED: All destructive actions route to Slack ONLY.\n")
    else:
        print("\n[FAIL] VERIFICATION 4 FAILED: See details above.\n")


# ===================================================================
# Main
# ===================================================================
if __name__ == "__main__":
    print(SEPARATOR + "INTEGRATIONS MODULE VERIFICATION" + SEPARATOR)

    prev_state = verify_1_live_slack()
    verify_2_mock_jira_pagerduty()
    verify_3_restart_no_duplicates(prev_state)
    verify_4_destructive_action_trace()

    print(SEPARATOR + "ALL VERIFICATIONS COMPLETE" + SEPARATOR)
