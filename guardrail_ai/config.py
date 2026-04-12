"""
Central configuration for Guardrail AI.
"""

# -----------------------------
# Batch Aggregation
# -----------------------------
DEFAULT_BATCH_SIZE = 50
MIN_BATCH_SIZE = 20
BATCH_TIMEOUT_SECONDS = 30
# -----------------------------
# Heartbeat Monitoring
# -----------------------------
HEARTBEAT_TIMEOUT_MINUTES = 10
HEARTBEAT_CHECK_INTERVAL_SECONDS = 60

# -----------------------------
# SHAP
# -----------------------------
MAX_SHAP_FEATURES = 5

# -----------------------------
# Threshold / Domain Settings
# -----------------------------
DOMAIN_CONFIG = {
    "healthcare": {
        "k": 2,
        "persistence": 0,
    },
    "finance": {
        "k": 2.5,
        "persistence": 1,
    },
    "standard": {
        "k": 3,
        "persistence": 3,
    },
}

# -----------------------------
# Logging
# -----------------------------
LOG_LEVEL = "INFO"