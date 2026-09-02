from app.services.operations import build_alert_codes


def test_operations_alerts_are_empty_for_healthy_runtime() -> None:
    assert build_alert_codes(
        oldest_queued_seconds=20,
        redis_queue_depth=1,
        failed_jobs_24h=0,
        provider_failures_24h=0,
    ) == []


def test_operations_alerts_surface_actionable_failures() -> None:
    assert build_alert_codes(
        oldest_queued_seconds=121,
        redis_queue_depth=21,
        failed_jobs_24h=2,
        provider_failures_24h=1,
    ) == [
        "redis_queue_backlog",
        "worker_queue_stale",
        "worker_failures_24h",
        "provider_failures_24h",
    ]


def test_operations_alerts_surface_redis_visibility_loss() -> None:
    assert build_alert_codes(
        oldest_queued_seconds=None,
        redis_queue_depth=None,
        failed_jobs_24h=0,
        provider_failures_24h=0,
    ) == ["redis_queue_unavailable"]
