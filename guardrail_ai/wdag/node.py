from typing import Dict, List



class Node:
    """
    Represents a WDAG vertex (stage in pipeline).
    Handles status, metrics, and dependency relationships.
    """

    VALID_STATUSES = {"green", "warning", "critical", "locked", "grey"}

    def __init__(self, name: str, owner: str) -> None:
        self.name = name
        self.owner = owner

        self.status: str = "green"
        self.metrics: Dict[str, Dict] = {}

        self.upstream: List["Node"] = []
        self.downstream: List["Node"] = []

        # history for persistence (used later if needed)
        self.status_history: List[str] = []

    # -----------------------------
    # Dependency Management
    # -----------------------------
    def add_downstream(self, node: "Node") -> None:
        # Prevent duplicate edges
        if node not in self.downstream:
            self.downstream.append(node)
        if self not in node.upstream:
            node.upstream.append(self)

    # -----------------------------
    # Metrics Update
    # -----------------------------
    def update_metrics(self, metrics: Dict[str, Dict]) -> None:
        self.metrics = metrics

    # -----------------------------
    # Status Update
    # -----------------------------
    def update_status(self, new_status: str) -> None:

        if new_status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {new_status}")

    # Hysteresis: avoid immediate flip from critical → green
        if self.status == "critical" and new_status == "green":
           if len(self.status_history) < 1 or self.status_history[-1] != "green":
               self.status_history.append("green")
               return  # wait for confirmation

        self.status = new_status
        self.status_history.append(new_status)
    # -----------------------------
    # Failure Handling
    # -----------------------------
    def mark_failure(self, failure: Dict) -> None:
        """
        Inject system failure (schema mismatch, crash, etc.)
        """
        self.update_status("critical")
        self.metrics = {
            "system_failure": failure
        }

    # -----------------------------
    # Lock Node (due to upstream failure)
    # -----------------------------
    def lock(self) -> None:
        self.update_status("locked")

    # -----------------------------
    # Reset Node (for recovery scenarios)
    # -----------------------------
    def reset(self) -> None:
        self.status = "green"
        self.metrics = {}

    # -----------------------------
    # Helper: Check if node is healthy
    # -----------------------------
    def is_healthy(self) -> bool:
        return self.status == "green"

    # -----------------------------
    # Representation
    # -----------------------------
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "owner": self.owner,
            "status": self.status,
            "metrics": self.metrics,
            "upstream": [n.name for n in self.upstream],
            "downstream": [n.name for n in self.downstream],
        }