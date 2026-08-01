"""
Jira Cloud REST API v3 client for creating governance decision tickets.

Authenticates via Basic auth (email + API token) and creates issues
in the configured Jira project. This module only creates tickets —
it never modifies, transitions, or deletes any Jira resources.
"""

import logging
import os
import time
from base64 import b64encode
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("integrations.jira_client")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

JIRA_BASE_URL: str = os.environ.get("JIRA_BASE_URL", "")
JIRA_EMAIL: str = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN: str = os.environ.get("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY: str = os.environ.get("JIRA_PROJECT_KEY", "")

MAX_RETRIES: int = 3
RETRY_BASE_DELAY_S: float = 2.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_header() -> str:
    """Return the Basic auth header value for Jira Cloud."""
    credentials = f"{JIRA_EMAIL}:{JIRA_API_TOKEN}"
    encoded = b64encode(credentials.encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


def _build_description_adf(
    decision: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build an Atlassian Document Format (ADF) description from a governance
    decision record.  The decision dict is a row from the governance history
    endpoint (top-level fields: diagnosis, severity, confidence, verdict,
    decision_json, etc.).
    """
    content_nodes: List[Dict[str, Any]] = []

    # --- Header paragraph ---
    content_nodes.append({
        "type": "paragraph",
        "content": [
            {"type": "text", "text": "Governance Decision Alert", "marks": [{"type": "strong"}]},
        ],
    })

    # --- Key fields ---
    diagnosis = decision.get("diagnosis", "UNKNOWN")
    severity = decision.get("severity", "UNKNOWN")
    confidence = decision.get("confidence", "N/A")
    recommended_action = decision.get("recommended_action", "UNKNOWN")
    model_id = decision.get("model_id", "UNKNOWN")
    verdict = decision.get("verdict", "")

    summary_text = (
        f"Model: {model_id}\n"
        f"Diagnosis: {diagnosis}\n"
        f"Severity: {severity}\n"
        f"Confidence: {confidence}\n"
        f"Recommended Action: {recommended_action}"
    )
    content_nodes.append({
        "type": "codeBlock",
        "attrs": {"language": "text"},
        "content": [{"type": "text", "text": summary_text}],
    })

    # --- Verdict ---
    if verdict:
        content_nodes.append({
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Verdict: ", "marks": [{"type": "strong"}]},
                {"type": "text", "text": verdict},
            ],
        })

    # --- Evidence items from decision_json.evidence ---
    decision_json = decision.get("decision_json") or {}
    evidence_items: List[Dict[str, Any]] = decision_json.get("evidence", [])

    if evidence_items:
        content_nodes.append({
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Evidence:", "marks": [{"type": "strong"}]},
            ],
        })

        bullet_items: List[Dict[str, Any]] = []
        for ev in evidence_items:
            signal = ev.get("signal", "?")
            status = ev.get("status", "?")
            detail = ev.get("detail", "")
            source = ev.get("source", "")
            strength = ev.get("strength", "")
            line = f"[{signal}] status={status}, detail={detail}, source={source}, strength={strength}"
            bullet_items.append({
                "type": "listItem",
                "content": [{
                    "type": "paragraph",
                    "content": [{"type": "text", "text": line}],
                }],
            })

        content_nodes.append({
            "type": "bulletList",
            "content": bullet_items,
        })

    return {
        "version": 1,
        "type": "doc",
        "content": content_nodes,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_issue(
    summary: str,
    description: str,
    issue_type: str = "Task",
    decision: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a Jira issue via the REST API v3.

    Parameters
    ----------
    summary : str
        Short summary line for the Jira issue.
    description : str
        Plain-text fallback (used only when *decision* is not provided).
    issue_type : str
        Jira issue type name (default ``"Task"``).
    decision : dict, optional
        Full governance decision record.  When provided the Jira description
        is built in rich ADF format from the decision fields.

    Returns
    -------
    dict
        The JSON response from Jira (contains ``key``, ``id``, ``self``).

    Raises
    ------
    requests.HTTPError
        On non-2xx response after all retries are exhausted.
    ValueError
        If required environment variables are missing.
    """
    if not all([JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY]):
        raise ValueError(
            "Jira integration requires JIRA_BASE_URL, JIRA_EMAIL, "
            "JIRA_API_TOKEN, and JIRA_PROJECT_KEY environment variables."
        )

    url = f"{JIRA_BASE_URL.rstrip('/')}/rest/api/3/issue"

    # Build description body — prefer rich ADF when we have the decision.
    if decision is not None:
        desc_body = _build_description_adf(decision)
    else:
        # Fallback: wrap plain text in minimal ADF
        desc_body = {
            "version": 1,
            "type": "doc",
            "content": [{
                "type": "paragraph",
                "content": [{"type": "text", "text": description}],
            }],
        }

    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary,
            "description": desc_body,
            "issuetype": {"name": issue_type},
        }
    }

    headers = {
        "Authorization": _auth_header(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    last_exception: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Jira create_issue attempt %d/%d — POST %s",
                attempt, MAX_RETRIES, url,
            )
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            logger.info(
                "Jira issue created: %s (key=%s)",
                result.get("self", ""), result.get("key", ""),
            )
            return result

        except requests.RequestException as exc:
            last_exception = exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            body = ""
            if hasattr(exc, "response") and exc.response is not None:
                try:
                    body = exc.response.text[:500]
                except Exception:
                    pass
            logger.warning(
                "Jira create_issue attempt %d/%d failed (status=%s): %s — %s",
                attempt, MAX_RETRIES, status, exc, body,
            )
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY_S * (2 ** (attempt - 1))
                logger.info("Retrying in %.1f seconds…", delay)
                time.sleep(delay)

    # All retries exhausted
    logger.error("Jira create_issue failed after %d attempts.", MAX_RETRIES)
    raise last_exception  # type: ignore[misc]
