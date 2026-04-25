from typing import Dict, List
from datetime import datetime, timedelta

from guardrail_ai.wdag.graph import WDAG
from guardrail_ai.config import HEARTBEAT_TIMEOUT_MINUTES

class HeartbeatMonitor:
    """
    Tracks node activity and marks nodes as grey if SDK stops sending data.
    """

    def __init__(self, graph: WDAG, timeout_minutes: int = HEARTBEAT_TIMEOUT_MINUTES) -> None:
        self.graph = graph
        self.timeout = timedelta(minutes=timeout_minutes)

        self.last_seen: Dict[str, datetime] = {}

    # -----------------------------
    # Update heartbeat
    # -----------------------------
    def ping(self, node_name: str) -> None:
        self.last_seen[node_name] = datetime.utcnow()

    # -----------------------------
    # Check for zombie nodes
    # -----------------------------
    def check_timeouts(self) -> List[str]:
    
        now = datetime.utcnow()
        timed_out_nodes = []

        for node_name, node in self.graph.nodes.items():

            last_seen = self.last_seen.get(node_name)

        # ✅ FIX 1: Skip nodes never seen (grace period)
            if last_seen is None:
               continue

        # timeout check
            if now - last_seen > self.timeout:
                node.update_status("grey")
                timed_out_nodes.append(node_name)

            

        return timed_out_nodes