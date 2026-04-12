from typing import Dict, List
from collections import defaultdict


class PersistenceManager:
    """
    Stores metric status history.
    Later replaceable with DB backend.
    """

    def __init__(self) -> None:
        self.metric_history: Dict[str, List[str]] = defaultdict(list)

    # -----------------------------
    # Save metric status
    # -----------------------------
    def save_metric_status(self, metric_name: str, status: str) -> None:
        self.metric_history[metric_name].append(status)

    # -----------------------------
    # Get recent history
    # -----------------------------
    def get_history(self, metric_name: str, limit: int = 5) -> List[str]:
        history = self.metric_history.get(metric_name, [])
        return history[-limit:]

    # -----------------------------
    # Reset storage
    # -----------------------------
    def reset(self) -> None:
        self.metric_history.clear()