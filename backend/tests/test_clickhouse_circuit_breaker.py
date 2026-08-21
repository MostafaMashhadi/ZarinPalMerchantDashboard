import time
from unittest.mock import MagicMock

from repositories.circuit_breaker import CircuitState, ClickHouseCircuitBreaker


def test_circuit_breaker_initial_state() -> None:
    breaker = ClickHouseCircuitBreaker()
    assert breaker.state == CircuitState.CLOSED


def test_circuit_breaker_trips_on_three_failures() -> None:
    breaker = ClickHouseCircuitBreaker(failure_threshold=3, failure_window_seconds=60.0, recovery_timeout_seconds=20.0)

    # 1st failure
    breaker.record_failure(is_timeout=True)
    assert breaker.state == CircuitState.CLOSED

    # 2nd failure
    breaker.record_failure(is_timeout=True)
    assert breaker.state == CircuitState.CLOSED

    # 3rd failure within 60s window -> trips OPEN
    breaker.record_failure(is_timeout=True)
    assert breaker.state == CircuitState.OPEN


def test_circuit_breaker_half_open_probe_and_recovery() -> None:
    # Use short recovery timeout for testing
    breaker = ClickHouseCircuitBreaker(failure_threshold=3, failure_window_seconds=60.0, recovery_timeout_seconds=0.1)

    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    # Wait for recovery timeout
    time.sleep(0.15)
    assert breaker.state == CircuitState.HALF_OPEN

    # Successful probe resets breaker to CLOSED
    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED


def test_circuit_breaker_half_open_failure_reopens() -> None:
    breaker = ClickHouseCircuitBreaker(failure_threshold=3, failure_window_seconds=60.0, recovery_timeout_seconds=0.1)

    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    time.sleep(0.15)
    assert breaker.state == CircuitState.HALF_OPEN

    # Failed probe trips back to OPEN
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN


def test_circuit_breaker_redis_cache_fallback_tagged() -> None:
    mock_redis = MagicMock()
    mock_redis.get.return_value = '{"merchant_key": "M215", "gross_volume": 5000000}'

    breaker = ClickHouseCircuitBreaker(
        failure_threshold=3,
        failure_window_seconds=60.0,
        recovery_timeout_seconds=20.0,
        redis_client=mock_redis,
    )

    # Trip the breaker
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    def failing_query():
        raise TimeoutError("ClickHouse timed out")

    res, is_fallback = breaker.execute_with_fallback(failing_query, "cache_m215")
    assert is_fallback is True
    assert res["data_freshness"] == "cached_fallback"
    assert res["gross_volume"] == 5000000


def test_successful_query_is_not_tagged_as_fallback() -> None:
    mock_redis = MagicMock()
    breaker = ClickHouseCircuitBreaker(redis_client=mock_redis)

    def success_query():
        return {"merchant_key": "M215", "gross_volume": 10000000}

    res, is_fallback = breaker.execute_with_fallback(success_query, "cache_m215")
    assert is_fallback is False
    assert "data_freshness" not in res or res.get("data_freshness") != "cached_fallback"
    assert res["gross_volume"] == 10000000
