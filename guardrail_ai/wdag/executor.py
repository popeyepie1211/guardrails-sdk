from typing import Dict, Any
import pandas as pd

from guardrail_ai.wdag.graph import WDAG
from guardrail_ai.wdag.failure import SystemFailure
from guardrail_ai.core.vitals_engine import VitalsEngine
from guardrail_ai.wdag.heartbeat import HeartbeatMonitor


class WDAGExecutor:
    """
    Orchestrates validation, metric computation, and WDAG updates.
    """

    def __init__(self, graph: WDAG, engine: VitalsEngine) -> None:
        self.graph = graph
        self.engine = engine
        self.heartbeat = HeartbeatMonitor(graph)

    # -----------------------------
    # Execute a node
    # -----------------------------
    def run(self, node_name: str, df: pd.DataFrame) -> Dict[str, Any]:
        self.heartbeat.ping(node_name)
        node = self.graph.get_node(node_name)

        try:
            # -----------------------------
            # Compute metrics
            # -----------------------------
            result = self.engine.compute_batch(df)

            metrics = result["metrics"]
            overall_status = result["overall_status"]

            # -----------------------------
            # Update node
            # -----------------------------
            node.update_metrics(metrics)
            status_map = {
            "normal": "green",
            "warning": "warning",
            "critical": "critical"
}
            node.update_status(status_map.get(overall_status, "green"))

            # -----------------------------
            # If critical → propagate
            # -----------------------------
            if overall_status == "critical":
                self.graph.propagate_impact(node)
            
            return {
                "node": node_name,
                "status": overall_status,
                "metrics": metrics,
            }

        except Exception as e:
            # -----------------------------
            # System failure handling
            # -----------------------------
            failure = SystemFailure.from_exception(e,
                                                   stage=node_name)

            self.graph.inject_failure(node_name, failure.to_dict())

            return {
                "node": node_name,
                "status": "critical",
                "error": failure.to_dict(),
            }