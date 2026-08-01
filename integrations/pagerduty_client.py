"""
PagerDuty Events API v2 client for triggering governance alerts.

Posts trigger events to the PagerDuty Events API v2 ``/v2/enqueue``
endpoint.  This module only triggers alerts — it never acknowledges,
resolves, or modifies any PagerDuty incident or service.
"""

import logging
import os
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger("integrations.pagerduty_client")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PAGERDUTY_ROUTING_KEY: str = os.environ.get("PAGERDUTY_ROUTING_KEY", "")
PAGERDUTY_EVENTS_URL: str = "https://events.pagerduty.com/v2/enqueue"

MAX_RETRIES: int = 3
RETRY_BASE_DELAY_S: float = 2.0

# Map governance severity → PagerDuty severity
# PagerDuty allows: critical, error, warning, info
_SEVERITY_MAP: Dict[str, str] = {
    "CRITICAL": "critical",
    "HIGH": "error",
    "MEDIUM": "warning",
    "LOW": "info",
    "INFO": "info",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def trigger_alert(
    summary: str,
    source: str,
    severity: str,
    dedup_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Trigger a PagerDuty alert via the Events API v2.

    Parameters
    ----------
    summary : str
        Human-readable summary of the alert (max 1024 chars).
    source : str
        The source of the alert (typically the model_id).
    severity : str
        Governance severity value (CRITICAL / HIGH / MEDIUM / LOW / INFO).
        Mapped to PagerDuty's allowed values.
    dedup_key : str, optional
        Deduplication key.  If omitted PagerDuty will auto-generate one.

    Returns
    -------
    dict
        The JSON response from PagerDuty (contains ``status``,
        ``message``, ``dedup_key``).

    Raises
    ------
    requests.HTTPError
        On non-2xx response after all retries are exhausted.
    ValueError
        If PAGERDUTY_ROUTING_KEY is not configured.
    """
    if not PAGERDUTY_ROUTING_KEY:
        raise ValueError(
            "PagerDuty integration requires the PAGERDUTY_ROUTING_KEY "
            "environment variable."
        )

    pd_severity = _SEVERITY_MAP.get(severity.upper(), "info")

    payload: Dict[str, Any] = {
        "routing_key": PAGERDUTY_ROUTING_KEY,
        "event_action": "trigger",
        "payload": {
            "summary": summary[:1024],
            "source": source,
            "severity": pd_severity,
            "component": "guardrails-governance",
            "class": "governance-decision",
        },
    }

    if dedup_key:
        payload["dedup_key"] = dedup_key

    last_exception: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "PagerDuty trigger_alert attempt %d/%d — source=%s severity=%s",
                attempt, MAX_RETRIES, source, pd_severity,
            )
            resp = requests.post(
                PAGERDUTY_EVENTS_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(
                "PagerDuty alert triggered: status=%s dedup_key=%s",
                result.get("status"), result.get("dedup_key"),
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
                "PagerDuty trigger_alert attempt %d/%d failed (status=%s): %s — %s",
                attempt, MAX_RETRIES, status, exc, body,
            )
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY_S * (2 ** (attempt - 1))
                logger.info("Retrying in %.1f seconds…", delay)
                time.sleep(delay)

    logger.error(
        "PagerDuty trigger_alert failed after %d attempts.", MAX_RETRIES,
    )
    raise last_exception  # type: ignore[misc]
