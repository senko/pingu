from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
import respx
from asgiref.sync import async_to_sync
from django.utils import timezone

from pingu.core.models import Check, CheckResult, Incident
from pingu.core.services import (
    evaluate_check_result,
    execute_check,
    execute_checks,
    get_check_status,
    get_checks_due,
    get_consecutive_failures,
    get_daily_availability,
    get_hourly_availability,
    get_monthly_availability,
    get_uptime_color,
    run_single_check,
)

# ---------------------------------------------------------------------------
# execute_check (mocked with respx, called via asyncio.run)
# ---------------------------------------------------------------------------


@respx.mock
def test_execute_check_success(check):
    respx.get("https://example.com").mock(return_value=httpx.Response(200, text="OK"))
    result = async_to_sync(execute_check)(check)

    assert result.is_success is True
    assert result.status_code == 200
    assert result.response_time is not None
    assert result.error_message == ""


@respx.mock
def test_execute_check_unexpected_status(check):
    respx.get("https://example.com").mock(return_value=httpx.Response(500, text="Error"))
    result = async_to_sync(execute_check)(check)

    assert result.is_success is False
    assert result.status_code == 500


@respx.mock
def test_execute_check_timeout(check):
    respx.get("https://example.com").mock(side_effect=httpx.TimeoutException("timed out"))
    result = async_to_sync(execute_check)(check)

    assert result.is_success is False
    assert result.status_code is None
    assert "timeout" in result.error_message.lower()


@respx.mock
def test_execute_check_connect_error(check):
    respx.get("https://example.com").mock(side_effect=httpx.ConnectError("refused"))
    result = async_to_sync(execute_check)(check)

    assert result.is_success is False
    assert result.status_code is None
    assert result.error_message == "refused"


@pytest.mark.django_db
@respx.mock
def test_execute_check_post_with_body(db, user):
    post_check = Check.objects.create(
        name="POST Check",
        url="https://example.com/api",
        method="POST",
        body='{"key": "value"}',
        expected_statuses=[201],
        timeout=5,
        interval=1,
        is_active=True,
        created_by=user,
    )
    respx.post("https://example.com/api").mock(return_value=httpx.Response(201, text="Created"))
    result = async_to_sync(execute_check)(post_check)

    assert result.is_success is True
    assert result.status_code == 201
    assert respx.calls[0].request.content == b'{"key": "value"}'


@pytest.mark.django_db
@respx.mock
def test_execute_check_custom_expected_statuses(db, user):
    """Custom expected_statuses should override defaults (gap 2.2)."""
    c = Check.objects.create(
        name="Custom Statuses",
        url="https://example.com/custom",
        method="GET",
        expected_statuses=[301],
        timeout=5,
        interval=1,
        is_active=True,
        created_by=user,
    )
    # 301 is in custom expected list — should be success
    respx.get("https://example.com/custom").mock(return_value=httpx.Response(301, text=""))
    result = async_to_sync(execute_check)(c)
    assert result.is_success is True

    # 200 is NOT in custom expected list — should be failure
    respx.get("https://example.com/custom").mock(return_value=httpx.Response(200, text="OK"))
    result = async_to_sync(execute_check)(c)
    assert result.is_success is False


@pytest.mark.django_db
@respx.mock
def test_execute_check_follows_redirects(db, user):
    """Verify that redirects are followed and the final status is used (gap 2.5)."""
    c = Check.objects.create(
        name="Redirect Check",
        url="https://example.com/redirect",
        method="GET",
        expected_statuses=[200],
        timeout=5,
        interval=1,
        is_active=True,
        created_by=user,
    )
    respx.get("https://example.com/redirect").mock(
        return_value=httpx.Response(
            301,
            headers={"Location": "https://example.com/final"},
        )
    )
    respx.get("https://example.com/final").mock(
        return_value=httpx.Response(200, text="OK")
    )
    result = async_to_sync(execute_check)(c)
    assert result.status_code == 200
    assert result.is_success is True


@pytest.mark.django_db
@respx.mock
def test_execute_check_default_expected_statuses(db, user):
    """When expected_statuses is empty, fall back to DEFAULT_EXPECTED_STATUSES."""
    c = Check.objects.create(
        name="Default Statuses",
        url="https://example.com/default",
        method="GET",
        expected_statuses=[],
        timeout=5,
        interval=1,
        is_active=True,
        created_by=user,
    )
    respx.get("https://example.com/default").mock(return_value=httpx.Response(204, text=""))
    result = async_to_sync(execute_check)(c)
    assert result.is_success is True


# ---------------------------------------------------------------------------
# execute_checks (fan-out)
# ---------------------------------------------------------------------------


@respx.mock
def test_execute_checks_multiple(check, check_no_alert):
    respx.get("https://example.com").mock(return_value=httpx.Response(200, text="OK"))
    respx.get("https://example.com/silent").mock(return_value=httpx.Response(200, text="OK"))
    results = async_to_sync(execute_checks)([check, check_no_alert])

    assert len(results) == 2
    assert all(r.is_success for r in results)


def test_execute_checks_global_timeout(check, check_no_alert):
    """Global timeout should produce failed results for all checks (gap 2.6)."""
    with patch("pingu.core.services.asyncio.wait_for", side_effect=TimeoutError):
        results = async_to_sync(execute_checks)([check, check_no_alert])

    assert len(results) == 2
    for r in results:
        assert r.is_success is False
        assert "Global timeout" in r.error_message


@respx.mock
def test_execute_checks_exception_in_gather(check):
    """Exception from a task in gather should produce a failed result (gap 2.7)."""
    with patch("pingu.core.services.execute_check", side_effect=RuntimeError("boom")):
        results = async_to_sync(execute_checks)([check])

    assert len(results) == 1
    assert results[0].is_success is False
    assert "boom" in results[0].error_message


# ---------------------------------------------------------------------------
# get_consecutive_failures
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_consecutive_failures_none(check):
    assert get_consecutive_failures(check) == 0


@pytest.mark.django_db
def test_consecutive_failures_all_success(check):
    now = timezone.now()
    for i in range(3):
        CheckResult.objects.create(
            check=check,
            timestamp=now - timedelta(minutes=i),
            status_code=200,
            is_success=True,
        )
    assert get_consecutive_failures(check) == 0


@pytest.mark.django_db
def test_consecutive_failures_counts_trailing(check):
    now = timezone.now()
    # oldest first: success, then 3 failures
    CheckResult.objects.create(
        check=check,
        timestamp=now - timedelta(minutes=4),
        status_code=200,
        is_success=True,
    )
    for i in range(3):
        CheckResult.objects.create(
            check=check,
            timestamp=now - timedelta(minutes=2 - i),
            status_code=500,
            is_success=False,
        )
    assert get_consecutive_failures(check) == 3


@pytest.mark.django_db
def test_consecutive_failures_stops_at_success(check):
    now = timezone.now()
    # 2 failures, then 1 success, then 1 failure (most recent)
    CheckResult.objects.create(
        check=check,
        timestamp=now - timedelta(minutes=4),
        status_code=500,
        is_success=False,
    )
    CheckResult.objects.create(
        check=check,
        timestamp=now - timedelta(minutes=3),
        status_code=500,
        is_success=False,
    )
    CheckResult.objects.create(
        check=check,
        timestamp=now - timedelta(minutes=2),
        status_code=200,
        is_success=True,
    )
    CheckResult.objects.create(
        check=check,
        timestamp=now - timedelta(minutes=1),
        status_code=500,
        is_success=False,
    )
    assert get_consecutive_failures(check) == 1


# ---------------------------------------------------------------------------
# evaluate_check_result — incident lifecycle & alerts
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_evaluate_alert_disabled_does_nothing(check_no_alert):
    now = timezone.now()
    result = CheckResult.objects.create(
        check=check_no_alert,
        timestamp=now,
        status_code=500,
        is_success=False,
    )
    evaluate_check_result(result)
    assert Incident.objects.count() == 0


@pytest.mark.django_db
def test_evaluate_opens_incident_at_threshold(check):
    now = timezone.now()
    # Create failures to meet the threshold (alert_threshold=2)
    for i in range(2):
        r = CheckResult.objects.create(
            check=check,
            timestamp=now - timedelta(minutes=1 - i),
            status_code=500,
            is_success=False,
        )

    with patch("pingu.alerts.backends.send_down_alert") as mock_notify:
        evaluate_check_result(r)

    assert Incident.objects.filter(check=check, ended_at__isnull=True).count() == 1
    mock_notify.assert_called_once()


@pytest.mark.django_db
def test_evaluate_does_not_duplicate_incident(check):
    now = timezone.now()
    # Pre-existing open incident
    Incident.objects.create(check=check, started_at=now - timedelta(hours=1))

    for i in range(3):
        r = CheckResult.objects.create(
            check=check,
            timestamp=now - timedelta(minutes=2 - i),
            status_code=500,
            is_success=False,
        )

    with patch("pingu.alerts.backends.send_down_alert") as mock_notify:
        evaluate_check_result(r)

    # Still only one open incident
    assert Incident.objects.filter(check=check, ended_at__isnull=True).count() == 1
    mock_notify.assert_not_called()


@pytest.mark.django_db
def test_evaluate_closes_incident_on_success(check):
    now = timezone.now()
    incident = Incident.objects.create(check=check, started_at=now - timedelta(hours=1))

    result = CheckResult.objects.create(
        check=check,
        timestamp=now,
        status_code=200,
        is_success=True,
    )
    with patch("pingu.alerts.backends.send_up_alert") as mock_notify:
        evaluate_check_result(result)

    incident.refresh_from_db()
    assert incident.ended_at == result.timestamp
    mock_notify.assert_called_once()


@pytest.mark.django_db
def test_evaluate_success_no_incident_does_nothing(check):
    now = timezone.now()
    result = CheckResult.objects.create(
        check=check,
        timestamp=now,
        status_code=200,
        is_success=True,
    )
    with patch("pingu.alerts.backends.send_up_alert") as mock_notify:
        evaluate_check_result(result)

    assert Incident.objects.count() == 0
    mock_notify.assert_not_called()


@pytest.mark.django_db
def test_evaluate_below_threshold_no_incident(check):
    """Failures below alert_threshold should NOT create an incident."""
    now = timezone.now()
    # Only 1 failure, threshold is 2
    r = CheckResult.objects.create(
        check=check,
        timestamp=now,
        status_code=500,
        is_success=False,
    )
    with patch("pingu.alerts.backends.send_down_alert") as mock_notify:
        evaluate_check_result(r)

    assert Incident.objects.count() == 0
    mock_notify.assert_not_called()


# ---------------------------------------------------------------------------
# get_checks_due
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_checks_due_never_run(check):
    """A check that has never run should be due."""
    due = get_checks_due()
    assert check in due


@pytest.mark.django_db
def test_get_checks_due_recently_run_not_due(check):
    """A check that just ran should NOT be due."""
    CheckResult.objects.create(
        check=check,
        timestamp=timezone.now(),
        status_code=200,
        is_success=True,
    )
    due = get_checks_due()
    assert check not in due


@pytest.mark.django_db
def test_get_checks_due_interval_elapsed(check):
    """A check whose interval has elapsed should be due."""
    CheckResult.objects.create(
        check=check,
        timestamp=timezone.now() - timedelta(minutes=check.interval + 1),
        status_code=200,
        is_success=True,
    )
    due = get_checks_due()
    assert check in due


@pytest.mark.django_db
def test_get_checks_due_inactive_excluded(db, user):
    """Inactive checks should never be returned as due."""
    inactive = Check.objects.create(
        name="Inactive",
        url="https://example.com/inactive",
        method="GET",
        is_active=False,
        created_by=user,
    )
    due = get_checks_due()
    assert inactive not in due


# ---------------------------------------------------------------------------
# get_check_status
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_check_status_paused(check):
    check.is_active = False
    check.save()
    assert get_check_status(check) == "paused"


@pytest.mark.django_db
def test_get_check_status_down(check):
    Incident.objects.create(check=check, started_at=timezone.now())
    assert get_check_status(check) == "down"


@pytest.mark.django_db
def test_get_check_status_unknown(check):
    """No results and no incidents => unknown."""
    assert get_check_status(check) == "unknown"


@pytest.mark.django_db
def test_get_check_status_up(check, success_result):
    assert get_check_status(check) == "up"


@pytest.mark.django_db
def test_get_check_status_paused_with_open_incident(check):
    """Paused check with open incident should show 'paused', not 'down' (gap 10.1)."""
    Incident.objects.create(check=check, started_at=timezone.now())
    check.is_active = False
    check.save()
    assert get_check_status(check) == "paused"


# ---------------------------------------------------------------------------
# get_daily_availability
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_daily_availability_all_success(check):
    today = date.today()
    day_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    for i in range(10):
        CheckResult.objects.create(
            check=check,
            timestamp=day_start + timedelta(minutes=i * 10),
            status_code=200,
            is_success=True,
        )
    stats = get_daily_availability(check, today)
    assert stats["uptime_pct"] == 100.0
    assert stats["total"] == 10
    assert stats["success"] == 10
    assert stats["failed"] == 0
    assert stats["has_data"] is True


@pytest.mark.django_db
def test_daily_availability_with_failures(check):
    today = date.today()
    day_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    for i in range(8):
        CheckResult.objects.create(
            check=check,
            timestamp=day_start + timedelta(minutes=i * 10),
            status_code=200,
            is_success=True,
        )
    for i in range(2):
        CheckResult.objects.create(
            check=check,
            timestamp=day_start + timedelta(minutes=80 + i * 10),
            status_code=500,
            is_success=False,
        )
    stats = get_daily_availability(check, today)
    assert stats["uptime_pct"] == 80.0
    assert stats["total"] == 10
    assert stats["failed"] == 2
    assert stats["has_data"] is True


@pytest.mark.django_db
def test_daily_availability_no_data(check):
    yesterday = date.today() - timedelta(days=1)
    stats = get_daily_availability(check, yesterday)
    assert stats["has_data"] is False
    assert stats["uptime_pct"] == 100.0


@pytest.mark.django_db
def test_daily_availability_falls_back_to_incidents(check):
    yesterday = date.today() - timedelta(days=1)
    day_start = timezone.make_aware(datetime.combine(yesterday, datetime.min.time()))
    # Incident covering half the day
    Incident.objects.create(
        check=check,
        started_at=day_start,
        ended_at=day_start + timedelta(hours=12),
    )
    stats = get_daily_availability(check, yesterday)
    assert stats["has_data"] is True
    assert stats["uptime_pct"] == 50.0
    assert stats["total"] == 0  # no check results


@pytest.mark.django_db
def test_daily_availability_fallback_with_open_incident(check):
    """Open (ongoing) incident should be included in daily fallback (gap 4.6)."""
    yesterday = date.today() - timedelta(days=1)
    day_start = timezone.make_aware(datetime.combine(yesterday, datetime.min.time()))
    # Open incident that started before the target day (no ended_at)
    Incident.objects.create(
        check=check,
        started_at=day_start,
    )
    stats = get_daily_availability(check, yesterday)
    assert stats["has_data"] is True
    assert stats["uptime_pct"] < 100.0


# ---------------------------------------------------------------------------
# get_hourly_availability
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_hourly_availability_returns_correct_count(check):
    result = get_hourly_availability(check, hours=6)
    assert len(result) == 6


@pytest.mark.django_db
def test_hourly_availability_with_data(check):
    now = timezone.now()
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    # 4 successes, 1 failure in the current hour
    for i in range(4):
        CheckResult.objects.create(
            check=check,
            timestamp=hour_start + timedelta(minutes=i * 5),
            status_code=200,
            is_success=True,
        )
    CheckResult.objects.create(
        check=check,
        timestamp=hour_start + timedelta(minutes=25),
        status_code=500,
        is_success=False,
    )
    result = get_hourly_availability(check, hours=1)
    assert len(result) == 1
    entry = result[0]
    assert entry["total"] == 5
    assert entry["failures"] == 1
    assert entry["uptime_pct"] == 80.0


@pytest.mark.django_db
def test_hourly_availability_chronological_order(check):
    """Hourly buckets should be in chronological order, oldest first (gap 4.5)."""
    result = get_hourly_availability(check, hours=3)
    assert len(result) == 3
    assert result[0]["hour_start"] < result[1]["hour_start"] < result[2]["hour_start"]


@pytest.mark.django_db
def test_hourly_availability_empty_hour(check):
    result = get_hourly_availability(check, hours=1)
    entry = result[0]
    assert entry["total"] == 0
    assert entry["uptime_pct"] == 100.0


# ---------------------------------------------------------------------------
# get_monthly_availability
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_monthly_availability_no_incidents(check):
    now = timezone.now()
    stats = get_monthly_availability(check, now.year, now.month)
    assert stats["uptime_pct"] == 100.0
    assert stats["incidents"] == 0
    assert stats["downtime_seconds"] == 0.0


@pytest.mark.django_db
def test_monthly_availability_with_incident(check):
    month_start = timezone.make_aware(datetime(2026, 1, 1))
    # 1 hour downtime in January 2026
    Incident.objects.create(
        check=check,
        started_at=month_start + timedelta(hours=1),
        ended_at=month_start + timedelta(hours=2),
    )
    stats = get_monthly_availability(check, 2026, 1)
    assert stats["incidents"] == 1
    assert stats["downtime_seconds"] == 3600.0
    assert stats["has_data"] is True
    # January has 31 days = 2678400 seconds
    expected_uptime = round(((2678400 - 3600) / 2678400) * 100, 2)
    assert stats["uptime_pct"] == expected_uptime


@pytest.mark.django_db
def test_monthly_availability_has_data_from_results(check):
    """has_data should be True when check results exist even without incidents."""
    month_start = timezone.make_aware(datetime(2026, 2, 1))
    CheckResult.objects.create(
        check=check,
        timestamp=month_start + timedelta(hours=1),
        status_code=200,
        is_success=True,
    )
    stats = get_monthly_availability(check, 2026, 2)
    assert stats["has_data"] is True
    assert stats["uptime_pct"] == 100.0


# ---------------------------------------------------------------------------
# run_single_check (sync wrapper — mock async execution)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@respx.mock
def test_run_single_check(check):
    respx.get("https://example.com").mock(return_value=httpx.Response(200, text="OK"))

    with patch("pingu.core.services.evaluate_check_result") as mock_eval:
        result = run_single_check(check)

    assert result.is_success is True
    assert result.status_code == 200
    assert result.pk is not None  # saved to DB
    assert CheckResult.objects.filter(pk=result.pk).exists()
    mock_eval.assert_called_once_with(result)


@pytest.mark.django_db
@respx.mock
def test_run_single_check_failure(check):
    respx.get("https://example.com").mock(side_effect=httpx.ConnectError("Connection refused"))

    with patch("pingu.core.services.evaluate_check_result") as mock_eval:
        result = run_single_check(check)

    assert result.is_success is False
    assert "Connection refused" in result.error_message
    assert result.pk is not None  # saved to DB
    assert CheckResult.objects.filter(pk=result.pk).exists()
    mock_eval.assert_called_once_with(result)


# ---------------------------------------------------------------------------
# get_uptime_color
# ---------------------------------------------------------------------------


def test_get_uptime_color_green():
    assert get_uptime_color(0.0) == "bg-green-500"


def test_get_uptime_color_yellow():
    assert get_uptime_color(0.5) == "bg-yellow-500"


def test_get_uptime_color_orange():
    assert get_uptime_color(3.0) == "bg-orange-500"


def test_get_uptime_color_red():
    assert get_uptime_color(10.0) == "bg-red-500"


# ---------------------------------------------------------------------------
# get_monthly_availability — December boundary
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_monthly_availability_december(check):
    """December should correctly set month_end to January 1 of next year."""
    month_start = timezone.make_aware(datetime(2025, 12, 1))
    Incident.objects.create(
        check=check,
        started_at=month_start + timedelta(hours=1),
        ended_at=month_start + timedelta(hours=2),
    )
    stats = get_monthly_availability(check, 2025, 12)
    assert stats["incidents"] == 1
    assert stats["downtime_seconds"] == 3600.0
    assert stats["has_data"] is True
    # December has 31 days = 2678400 seconds
    expected_uptime = round(((2678400 - 3600) / 2678400) * 100, 2)
    assert stats["uptime_pct"] == expected_uptime


# ---------------------------------------------------------------------------
# execute_check — generic HTTPError
# ---------------------------------------------------------------------------


@respx.mock
def test_execute_check_generic_http_error(check):
    respx.get("https://example.com").mock(side_effect=httpx.HTTPError("something broke"))
    result = async_to_sync(execute_check)(check)

    assert result.is_success is False
    assert result.status_code is None
    assert "something broke" in result.error_message
