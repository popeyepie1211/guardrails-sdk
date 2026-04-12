import time

from guardrail_ai.wdag.executor import WDAGExecutor
from guardrail_ai.config import HEARTBEAT_CHECK_INTERVAL_SECONDS


class WDAGMonitor:
    """
    Background monitor for heartbeat timeout checks.
    """

    def __init__(self, executor: WDAGExecutor, interval_seconds: int = HEARTBEAT_CHECK_INTERVAL_SECONDS) -> None:
        self.executor = executor
        self.interval = interval_seconds

    def start(self, cycles: int = 5) -> None:
        for _ in range(cycles):
            timed_out_nodes = self.executor.heartbeat.check_timeouts()

            if timed_out_nodes:
              print(f"[Heartbeat Alert] Timed out nodes: {timed_out_nodes}")

            time.sleep(self.interval)