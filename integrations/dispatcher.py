"""
Governance Decision Dispatcher

Polls the dbapi governance history endpoint for each watched model and
dispatches notifications to Slack, Jira, or PagerDuty based on the
``recommended_action`` field.

CRITICAL SAFETY POLICY
----------------------
This module ONLY reads governance data and sends *notifications*.  There
is zero code in this file (or anywhere in the integrations package) that
can roll back, retrain, isolate, restrict, or otherwise modify any model
or production system.  Actions that imply destructive/corrective changes
are routed to Slack with an explicit "manual human execution required"
warning — nothing more.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from integrations import jira_client, pagerduty_client, slack_client

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("integrations.dispatcher")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WATCHED_MODEL_IDS: List[str] = [
    mid.strip()
    for mid in os.environ.get("WATCHED_MODEL_IDS", "").split(",")
    if mid.strip()
]

POLL_INTERVAL_SECONDS: int = int(
    os.environ.get("POLL_INTERVAL_SECONDS", "60")
)

DBAPI_BASE_URL: str = os.environ.get("DBAPI_BASE_URL", "http://localhost:8002")

STATE_FILE: Path = Path(__file__).resolve().parent / "state.json"

# ---------------------------------------------------------------------------
# Handler functions (thin wrappers that translate a decision → client call)
# ---------------------------------------------------------------------------


def _handle_jira(decision: Dict[str, Any]) -> None:
    """Create a Jira ticket for an investigation-class governance decision."""
    model_id = decision.get("model_id", "UNKNOWN")
    severity = decision.get("severity", "UNKNOWN")
    diagnosis = decision.get("diagnosis", "UNKNOWN")
    summary = f"[{severity}] {diagnosis} — {model_id}"

    jira_client.create_issue(
        summary=summary,
        description="",  # ADF is built from decision
        issue_type="Task",
        decision=decision,
    )
    logger.info(
        "Jira ticket created for model_id=%s action=%s",
        model_id, decision.get("recommended_action"),
    )


def _handle_pagerduty(decision: Dict[str, Any]) -> None:
    """Trigger a PagerDuty alert for infrastructure/security decisions."""
    model_id = decision.get("model_id", "UNKNOWN")
    severity = decision.get("severity", "UNKNOWN")
    diagnosis = decision.get("diagnosis", "UNKNOWN")
    recommended_action = decision.get("recommended_action", "UNKNOWN")
    batch_id = decision.get("batch_id", "")

    summary = (
        f"[{severity}] {diagnosis} — {model_id}: "
        f"recommended action is {recommended_action}"
    )
    dedup_key = f"guardrails-{model_id}-{batch_id}" if batch_id else None

    pagerduty_client.trigger_alert(
        summary=summary,
        source=model_id,
        severity=severity,
        dedup_key=dedup_key,
    )
    logger.info(
        "PagerDuty alert triggered for model_id=%s action=%s",
        model_id, recommended_action,
    )


def _handle_slack(decision: Dict[str, Any], *, manual: bool = False) -> None:
    """Send a Slack notification for a governance decision."""
    model_id = decision.get("model_id", "UNKNOWN")
    slack_client.send_message(
        model_id=model_id,
        decision=decision,
        is_manual_action_required=manual,
    )
    logger.info(
        "Slack message sent for model_id=%s action=%s manual=%s",
        model_id, decision.get("recommended_action"), manual,
    )


# ---------------------------------------------------------------------------
# Composite handler helpers
# ---------------------------------------------------------------------------

def _handle_slack_only_manual(decision: Dict[str, Any]) -> None:
    """Slack ONLY — with explicit human-action-required warning.

    Used for destructive/corrective actions (RETRAIN_MODEL, ROLLBACK_MODEL,
    ISOLATE_MODEL, TEMPORARILY_RESTRICT_MODEL, RETRAIN_WITH_RECENT_DATA).
    This function intentionally does NOT call jira_client, pagerduty_client,
    or any execution logic.
    """
    _handle_slack(decision, manual=True)


def _handle_slack_and_jira(decision: Dict[str, Any]) -> None:
    """Slack notification + Jira ticket (for HUMAN_GOVERNANCE_REVIEW)."""
    _handle_slack(decision, manual=False)
    _handle_jira(decision)


# ---------------------------------------------------------------------------
# ACTION_MAP — maps GovernanceAction string values to handler(s)
#
# Source of truth for enum values:
#   guardrail_ai/digital_judge/models.py  →  GovernanceAction
#
# SAFETY:  Destructive/corrective actions route ONLY to Slack with a
#          manual-action-required warning.  No execution function exists.
# ---------------------------------------------------------------------------

ACTION_MAP: Dict[str, Callable[[Dict[str, Any]], None]] = {
    # Investigation / review → Jira ticket
    "INVESTIGATE_DRIFT":       _handle_jira,
    "REVIEW_FAIRNESS":         _handle_jira,
    "REVIEW_DATA_PIPELINE":    _handle_jira,
    "VALIDATE_INPUT_SOURCE":   _handle_jira,
    "RUN_BIAS_AUDIT":          _handle_jira,
    "REVIEW_PRIVACY_RISK":     _handle_jira,
    "REVIEW_EXPLAINABILITY":   _handle_jira,

    # Infrastructure / security → PagerDuty alert
    "CHECK_INFRASTRUCTURE":    _handle_pagerduty,
    "SECURITY_INVESTIGATION":  _handle_pagerduty,

    # Simple notification → Slack only
    "NOTIFY_OWNER":            lambda d: _handle_slack(d, manual=False),

    # Human governance review → Slack + Jira
    "HUMAN_GOVERNANCE_REVIEW": _handle_slack_and_jira,

    # Destructive / corrective actions → Slack ONLY (manual warning)
    # These NEVER call jira_client, pagerduty_client, or any execution logic.
    "RETRAIN_MODEL":              _handle_slack_only_manual,
    "ROLLBACK_MODEL":             _handle_slack_only_manual,
    "ISOLATE_MODEL":              _handle_slack_only_manual,
    "TEMPORARILY_RESTRICT_MODEL": _handle_slack_only_manual,
    "RETRAIN_WITH_RECENT_DATA":   _handle_slack_only_manual,

    # NO_ACTION → handled explicitly in the dispatch loop (log only)
}


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def _load_state() -> Dict[str, str]:
    """Load last-processed timestamps from disk."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            logger.info("Loaded state from %s: %s", STATE_FILE, state)
            return state
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read state file %s: %s", STATE_FILE, exc)
    return {}


def _save_state(state: Dict[str, str]) -> None:
    """Persist last-processed timestamps to disk (atomic-ish write)."""
    tmp_path = STATE_FILE.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        tmp_path.replace(STATE_FILE)
        logger.debug("State saved to %s", STATE_FILE)
    except OSError as exc:
        logger.error("Failed to save state to %s: %s", STATE_FILE, exc)


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------

def _fetch_history(model_id: str) -> List[Dict[str, Any]]:
    """Fetch governance decision history for a single model_id."""
    url = f"{DBAPI_BASE_URL.rstrip('/')}/api/governance/history"
    params = {"model_id": model_id, "limit": 100, "hours": 720}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # The endpoint returns a list directly
    if isinstance(data, list):
        return data
    # Defensive: some wrappers may nest under a key
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    logger.warning(
        "Unexpected response shape from governance/history for %s: %s",
        model_id, type(data),
    )
    return []


def _parse_time(time_str: str) -> datetime:
    """Parse an ISO-8601 timestamp string to a timezone-aware datetime."""
    # Handle the format: 2026-07-31T16:33:09.256878+00:00
    return datetime.fromisoformat(time_str)


def _poll_model(model_id: str, state: Dict[str, str]) -> None:
    """
    Poll governance history for one model_id, dispatch new decisions,
    and update state after each successfully dispatched item.
    """
    logger.info("Polling governance history for model_id=%s", model_id)

    decisions = _fetch_history(model_id)
    if not decisions:
        logger.info("No decisions returned for model_id=%s", model_id)
        return

    last_processed = state.get(model_id)
    last_processed_dt: Optional[datetime] = None
    if last_processed:
        try:
            last_processed_dt = _parse_time(last_processed)
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Invalid last_processed time for %s: %s — treating as none",
                model_id, exc,
            )

    # Decisions come most-recent-first; reverse to process oldest-first
    decisions_asc = list(reversed(decisions))

    new_count = 0

    for decision in decisions_asc:
        decision_time_str = decision.get("time")
        if not decision_time_str:
            logger.warning(
                "Decision missing 'time' field for model_id=%s, skipping: %s",
                model_id, decision.get("batch_id", "?"),
            )
            continue

        try:
            decision_dt = _parse_time(decision_time_str)
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Unparseable decision time for model_id=%s: %s — skipping",
                model_id, exc,
            )
            continue

        # Skip already-processed decisions
        if last_processed_dt is not None and decision_dt <= last_processed_dt:
            continue

        recommended_action = decision.get("recommended_action", "")
        batch_id = decision.get("batch_id", "?")

        # NO_ACTION or unrecognised → log only
        if recommended_action == "NO_ACTION" or recommended_action == "":
            logger.info(
                "Skipping decision (NO_ACTION/empty) for model_id=%s "
                "batch_id=%s time=%s",
                model_id, batch_id, decision_time_str,
            )
            # Still update state so we don't re-process on next poll
            state[model_id] = decision_time_str
            _save_state(state)
            continue

        handler = ACTION_MAP.get(recommended_action)

        if handler is None:
            # Unrecognised action value → log only, no external call
            logger.warning(
                "Unrecognised recommended_action '%s' for model_id=%s "
                "batch_id=%s — logging only, no notification sent.",
                recommended_action, model_id, batch_id,
            )
            state[model_id] = decision_time_str
            _save_state(state)
            continue

        # Dispatch to the handler
        try:
            logger.info(
                "Dispatching decision: model_id=%s action=%s batch_id=%s "
                "time=%s",
                model_id, recommended_action, batch_id, decision_time_str,
            )
            handler(decision)
            new_count += 1
        except Exception as exc:
            # Log the failure but do NOT crash the loop.  The decision will
            # NOT be marked as processed so it will be retried next cycle.
            logger.error(
                "Failed to dispatch decision for model_id=%s action=%s "
                "batch_id=%s: %s",
                model_id, recommended_action, batch_id, exc,
                exc_info=True,
            )
            # Do NOT update state — we want to retry this decision next poll.
            continue

        # Successfully dispatched — update state
        state[model_id] = decision_time_str
        _save_state(state)

    logger.info(
        "Finished polling model_id=%s — %d new decision(s) dispatched.",
        model_id, new_count,
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run() -> None:
    """Entry point — run the polling loop forever."""
    if not WATCHED_MODEL_IDS:
        logger.error(
            "WATCHED_MODEL_IDS is empty or not set.  Nothing to poll. "
            "Set it to a comma-separated list of model IDs."
        )
        sys.exit(1)

    logger.info(
        "Dispatcher starting — watching %d model(s): %s | poll interval: %ds",
        len(WATCHED_MODEL_IDS),
        ", ".join(WATCHED_MODEL_IDS),
        POLL_INTERVAL_SECONDS,
    )

    state = _load_state()

    while True:
        for model_id in WATCHED_MODEL_IDS:
            try:
                _poll_model(model_id, state)
            except Exception as exc:
                # Per-model isolation: one model's failure must not stop others
                logger.error(
                    "Error polling model_id=%s: %s", model_id, exc,
                    exc_info=True,
                )

        logger.info("Sleeping %d seconds until next poll…", POLL_INTERVAL_SECONDS)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
