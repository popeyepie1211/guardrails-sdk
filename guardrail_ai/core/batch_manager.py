from typing import List
import pandas as pd
from guardrail_ai.config import DEFAULT_BATCH_SIZE, MIN_BATCH_SIZE, BATCH_TIMEOUT_SECONDS

from typing import List, Optional
import pandas as pd
from datetime import datetime, timedelta


class BatchManager:
    """
    Collects streaming data and forms batches for stable metric computation.
    Supports:
    ✔ size-based batching
    ✔ time-based batching
    ✔ minimum batch threshold
    """

    def __init__(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
        min_batch_size: int = MIN_BATCH_SIZE,
        timeout_seconds: int = BATCH_TIMEOUT_SECONDS,
    ) -> None:

        self.batch_size = batch_size
        self.min_batch_size = min_batch_size
        self.timeout = timedelta(seconds=timeout_seconds)

        self.buffer: List[pd.DataFrame] = []
        self.last_flush_time = datetime.utcnow()

    # -----------------------------
    # Add data
    # -----------------------------
    def add(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        self.buffer.append(df)

        total_rows = sum(len(chunk) for chunk in self.buffer)
        now = datetime.utcnow()

        # 1️⃣ Size-based trigger
        if total_rows >= self.batch_size:
            return self._flush()

        # 2️⃣ Time-based trigger (with safety)
        if (
            now - self.last_flush_time >= self.timeout
            and total_rows >= self.min_batch_size
        ):
            return self._flush()

        return None

    # -----------------------------
    # Flush buffer
    # -----------------------------
    def _flush(self) -> pd.DataFrame:
        batch = pd.concat(self.buffer, ignore_index=True)
        self.buffer.clear()
        self.last_flush_time = datetime.utcnow()
        return batch

    # -----------------------------
    # Force flush (end of stream)
    # -----------------------------
    def flush(self) -> Optional[pd.DataFrame]:
        if not self.buffer:
            return None
        return self._flush()