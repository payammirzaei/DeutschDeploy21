from datetime import UTC, datetime

from app.services.engagement import _badges, _event_xp, _streak_metrics


def test_event_xp_is_bounded_and_effort_weighted() -> None:
    assert _event_xp(-20) == 10
    assert _event_xp(0) == 10
    assert _event_xp(60) == 13
    assert _event_xp(100) == 15
    assert _event_xp(180) == 15


def test_streak_metrics_keeps_yesterday_alive_until_today_ends() -> None:
    now = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
    timestamps = [
        datetime(2026, 8, 30, 10, 0, tzinfo=UTC),
        datetime(2026, 8, 31, 10, 0, tzinfo=UTC),
        datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
    ]

    current, longest = _streak_metrics(timestamps, now=now)

    assert current == 3
    assert longest == 3


def test_streak_metrics_resets_current_after_a_missed_day() -> None:
    now = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
    timestamps = [
        datetime(2026, 8, 30, 10, 0, tzinfo=UTC),
        datetime(2026, 8, 31, 10, 0, tzinfo=UTC),
        datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
    ]

    current, longest = _streak_metrics(timestamps, now=now)

    assert current == 0
    assert longest == 3


def test_badges_are_derived_without_persisted_gamification_state() -> None:
    badges = {badge.key: badge for badge in _badges(25, 4, 7)}

    assert badges["first_rep"].earned is True
    assert badges["reps_25"].earned is True
    assert badges["reps_100"].earned is False
    assert badges["streak_3"].earned is True
    assert badges["streak_7"].progress_current == 4
    assert badges["mastery_10"].earned is False
