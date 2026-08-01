"""
Slack incoming webhook client for governance decision notifications.

Sends Block Kit formatted messages to a Slack channel.  This module only
posts messages — it never reads channels, manages users, or modifies
any Slack workspace configuration.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("integrations.slack_client")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SLACK_WEBHOOK_URL: str = os.environ.get("SLACK_WEBHOOK_URL", "")
DBAPI_BASE_URL: str = os.environ.get("DBAPI_BASE_URL", "http://localhost:8002")

MAX_RETRIES: int = 3
RETRY_BASE_DELAY_S: float = 2.0

# Severity → emoji mapping
_SEVERITY_EMOJI = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "MEDIUM": "🟡",
    "LOW": "🟢",
    "INFO": "ℹ️",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_blocks(
    model_id: str,
    decision: Dict[str, Any],
    is_manual_action_required: bool = False,
) -> List[Dict[str, Any]]:
    """
    Build Slack Block Kit blocks from a governance decision record.
    """
    diagnosis = decision.get("diagnosis", "UNKNOWN")
    severity = decision.get("severity", "UNKNOWN")
    confidence = decision.get("confidence", "N/A")
    recommended_action = decision.get("recommended_action", "UNKNOWN")
    verdict = decision.get("verdict", "")
    emoji = _SEVERITY_EMOJI.get(severity, "❓")

    report_url = (
        f"{DBAPI_BASE_URL.rstrip('/')}"
        f"/api/governance/report/latest?model_id={model_id}"
    )

    blocks: List[Dict[str, Any]] = []

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"{emoji} Governance Alert — {model_id}",
            "emoji": True,
        },
    })

    # Key fields
    fields_text = (
        f"*Diagnosis:* `{diagnosis}`\n"
        f"*Severity:* `{severity}`\n"
        f"*Confidence:* `{confidence}`\n"
        f"*Recommended Action:* `{recommended_action}`"
    )
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": fields_text},
    })

    # Verdict (truncate to 2900 chars to stay under Slack block limits)
    if verdict:
        truncated = verdict[:2900]
        if len(verdict) > 2900:
            truncated += "…"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Verdict:* {truncated}"},
        })

    # Manual action warning
    if is_manual_action_required:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "⚠️ *This action requires manual human execution — "
                    "no automated action has been taken.* ⚠️\n"
                    "A human operator must review this alert and decide "
                    "whether to proceed with the recommended action."
                ),
            },
        })

    # Report link
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"<{report_url}|📄 View Full Governance Report>",
        },
    })

    # Context footer
    batch_id = decision.get("batch_id", "N/A")
    decision_time = decision.get("time", "N/A")
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"Batch: `{batch_id}` | Time: `{decision_time}`",
        }],
    })

    return blocks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_message(
    model_id: str,
    decision: Dict[str, Any],
    is_manual_action_required: bool = False,
) -> Dict[str, Any]:
    """
    Post a governance decision notification to Slack via incoming webhook.

    Parameters
    ----------
    model_id : str
        The model identifier.
    decision : dict
        Full governance decision record from the history endpoint.
    is_manual_action_required : bool
        When True, appends a prominent warning that the recommended action
        requires manual human execution and that no automated action has
        been taken.

    Returns
    -------
    dict
        ``{"ok": True}`` on success.

    Raises
    ------
    requests.HTTPError
        On non-2xx response after all retries are exhausted.
    ValueError
        If SLACK_WEBHOOK_URL is not configured.
    """
    if not SLACK_WEBHOOK_URL:
        raise ValueError(
            "Slack integration requires the SLACK_WEBHOOK_URL environment variable."
        )

    blocks = _build_blocks(model_id, decision, is_manual_action_required)

    # Fallback text for notifications / accessibility
    fallback_text = (
        f"Governance Alert — {model_id}: "
        f"{decision.get('diagnosis', '?')} ({decision.get('severity', '?')})"
    )

    payload = {
        "text": fallback_text,
        "blocks": blocks,
    }

    last_exception: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Slack send_message attempt %d/%d for model_id=%s",
                attempt, MAX_RETRIES, model_id,
            )
            resp = requests.post(
                SLACK_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            logger.info(
                "Slack message sent successfully for model_id=%s", model_id,
            )
            return {"ok": True}

        except requests.RequestException as exc:
            last_exception = exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning(
                "Slack send_message attempt %d/%d failed (status=%s): %s",
                attempt, MAX_RETRIES, status, exc,
            )
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY_S * (2 ** (attempt - 1))
                logger.info("Retrying in %.1f seconds…", delay)
                time.sleep(delay)

    logger.error(
        "Slack send_message failed after %d attempts for model_id=%s.",
        MAX_RETRIES, model_id,
    )
    raise last_exception  # type: ignore[misc]
