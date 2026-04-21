import logging
import threading
import time
from collections import deque
from typing import Deque, Dict, Optional, Tuple


logger = logging.getLogger(__name__)


class HistoryAnalyzeRateLimiter:
    def __init__(self, window_seconds: int, max_requests: int) -> None:
        self.window_seconds = max(1, int(window_seconds))
        self.max_requests = max(1, int(max_requests))
        self._events: Dict[int, Deque[float]] = {}
        self._lock = threading.Lock()

    def try_acquire(self, history_id: int, now: Optional[float] = None) -> Tuple[bool, int]:
        current = now if now is not None else time.time()
        with self._lock:
            q = self._events.setdefault(history_id, deque())
            cutoff = current - self.window_seconds
            while q and q[0] <= cutoff:
                q.popleft()

            if len(q) >= self.max_requests:
                return False, len(q)

            q.append(current)
            return True, len(q)


def log_rate_limit_hit(
    *,
    history_id: int,
    user_employee_id: str,
    session_id: Optional[str],
    mode: str,
    window_seconds: int,
    threshold: int,
    current_count: int,
) -> None:
    logger.warning(
        "AI 分析限流命中 history_id=%s user=%s session_id=%s mode=%s window_seconds=%s threshold=%s current_count=%s",
        history_id,
        user_employee_id,
        session_id or "",
        mode,
        window_seconds,
        threshold,
        current_count,
    )
