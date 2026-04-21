from backend.services.ai_rate_limit_service import HistoryAnalyzeRateLimiter


def test_history_rate_limit_threshold_and_window() -> None:
    limiter = HistoryAnalyzeRateLimiter(window_seconds=60, max_requests=10)
    now = 1000.0
    for _ in range(10):
        allowed, count = limiter.try_acquire(history_id=1, now=now)
        assert allowed is True
        assert count <= 10

    allowed, count = limiter.try_acquire(history_id=1, now=now)
    assert allowed is False
    assert count == 10

    # 窗口滑出后恢复
    allowed, count = limiter.try_acquire(history_id=1, now=1061.0)
    assert allowed is True
    assert count == 1


def test_history_rate_limit_isolated_by_history_id() -> None:
    limiter = HistoryAnalyzeRateLimiter(window_seconds=60, max_requests=2)
    now = 2000.0

    assert limiter.try_acquire(history_id=100, now=now)[0] is True
    assert limiter.try_acquire(history_id=100, now=now)[0] is True
    assert limiter.try_acquire(history_id=100, now=now)[0] is False

    # 不同 history_id 不受影响
    assert limiter.try_acquire(history_id=200, now=now)[0] is True
