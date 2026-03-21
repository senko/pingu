from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

import httpx
from asgiref.sync import async_to_sync
from django.conf import settings
from django.db.models import Max
from django.utils import timezone

from pingu.core.models import Check, CheckResult, Incident

logger = logging.getLogger(__name__)

DEFAULT_EXPECTED_STATUSES: list[int] = [200, 201, 204]


# ---------------------------------------------------------------------------
# Async HTTP execution
# ---------------------------------------------------------------------------


async def execute_check(check: Check) -> CheckResult:
    """Perform a single HTTP request and return an *unsaved* CheckResult."""
    expected = check.expected_statuses if check.expected_statuses else DEFAULT_EXPECTED_STATUSES
    now = timezone.now()

    # Build request kwargs
    kwargs: dict = {
        "method": check.method,
        "url": check.url,
        "headers": check.headers or {},
        "timeout": float(check.timeout),
        "follow_redirects": True,
    }
    if check.method in ("POST", "PUT", "PATCH") and check.body:
        kwargs["content"] = check.body

    status_code: int | None = None
    response_time: Decimal | None = None
    is_success = False
    error_message = ""

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.request(**kwargs)
            elapsed = resp.elapsed.total_seconds()
            status_code = resp.status_code
            response_time = Decimal(str(round(elapsed, 3)))
            is_success = status_code in expected
    except httpx.TimeoutException:
        error_message = f"Connection timeout after {check.timeout}s"
    except httpx.ConnectError as exc:
        error_message = str(exc)
    except httpx.HTTPError as exc:
        error_message = str(exc)

    return CheckResult(
        check=check,
        timestamp=now,
        status_code=status_code,
        response_time=response_time,
        is_success=is_success,
        error_message=error_message,
    )


async def execute_checks(checks: list[Check]) -> list[CheckResult]:
    """Fan out checks concurrently, bounded by CHECK_GLOBAL_TIMEOUT."""
    global_timeout = getattr(settings, "CHECK_GLOBAL_TIMEOUT", 30)
    tasks = [execute_check(check) for check in checks]
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=float(global_timeout),
        )
    except asyncio.TimeoutError:
        logger.error("Global timeout (%ds) exceeded while running checks", global_timeout)
        # Return whatever completed; create timeout results for the rest
        results = []
        for check in checks:
            results.append(
                CheckResult(
                    check=check,
                    timestamp=timezone.now(),
                    status_code=None,
                    response_time=None,
                    is_success=False,
                    error_message=f"Global timeout ({global_timeout}s) exceeded",
                )
            )

    # Convert any exceptions from gather into failed CheckResults
    final: list[CheckResult] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            check = checks[i]
            final.append(
                CheckResult(
                    check=check,
                    timestamp=timezone.now(),
                    status_code=None,
                    response_time=None,
                    is_success=False,
                    error_message=str(result),
                )
            )
        else:
            final.append(result)
    return final


# ---------------------------------------------------------------------------
# Sync wrappers
# ---------------------------------------------------------------------------


def run_single_check(check: Check) -> CheckResult:
    """Synchronous wrapper: execute check, save result, evaluate."""
    result = async_to_sync(execute_check)(check)
    result.save()
    evaluate_check_result(result)
    return result


# ---------------------------------------------------------------------------
# Result evaluation & incident management
# ---------------------------------------------------------------------------


def evaluate_check_result(result: CheckResult) -> None:
    """After a result is saved: manage incidents and fire alerts."""
    # Import here to avoid circular imports at module level
    from pingu.alerts.backends import notify_down, notify_up

    check = result.check
    if not check.alert_enabled:
        return

    consecutive = get_consecutive_failures(check)
    open_incident = check.incidents.filter(ended_at__isnull=True).first()

    if not result.is_success:
        # Check if we've hit the threshold and no incident is already open
        if consecutive >= check.alert_threshold and open_incident is None:
            incident = Incident.objects.create(
                check=check,
                started_at=result.timestamp,
                threshold_result=result,
            )
            notify_down(check, incident, consecutive)
    else:
        # Success: close any open incident
        if open_incident is not None:
            open_incident.ended_at = result.timestamp
            open_incident.save(update_fields=["ended_at"])
            notify_up(check, open_incident)


def get_consecutive_failures(check: Check) -> int:
    """Count consecutive failed results from the most recent backwards."""
    recent_results = check.results.order_by("-timestamp").values_list("is_success", flat=True)[:100]
    count = 0
    for success in recent_results:
        if success:
            break
        count += 1
    return count


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


def get_checks_due() -> list[Check]:
    """Return active checks whose interval has elapsed since their last result."""
    now = timezone.now()
    checks = (
        Check.objects.filter(is_active=True)
        .annotate(last_run=Max("results__timestamp"))
    )
    due: list[Check] = []
    for check in checks:
        if check.last_run is None:
            # Never executed
            due.append(check)
        else:
            next_run = check.last_run + timedelta(minutes=check.interval)
            if next_run <= now:
                due.append(check)
    return due


# ---------------------------------------------------------------------------
# Availability & statistics
# ---------------------------------------------------------------------------


def get_daily_availability(check: Check, target_date: date) -> dict:
    """Return availability stats for a single day.

    Returns: {uptime_pct, total, success, failed, has_data}
    Falls back to Incident data if CheckResult records have been purged.
    """
    day_start = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
    day_end = day_start + timedelta(days=1)

    results = check.results.filter(timestamp__gte=day_start, timestamp__lt=day_end)
    total = results.count()

    if total > 0:
        success = results.filter(is_success=True).count()
        failed = total - success
        uptime_pct = round((success / total) * 100, 2) if total else 100.0
        return {
            "uptime_pct": uptime_pct,
            "total": total,
            "success": success,
            "failed": failed,
            "has_data": True,
        }

    # Fall back to incidents
    from django.db.models import Q

    incidents = check.incidents.filter(
        started_at__lt=day_end,
    ).filter(
        Q(ended_at__gt=day_start) | Q(ended_at__isnull=True)
    )

    if not incidents.exists():
        # No results and no incidents — we have no data for this day
        # But if the check existed, treat it as unknown
        if check.created_at and check.created_at < day_end:
            return {
                "uptime_pct": 100.0,
                "total": 0,
                "success": 0,
                "failed": 0,
                "has_data": False,
            }
        return {
            "uptime_pct": 100.0,
            "total": 0,
            "success": 0,
            "failed": 0,
            "has_data": False,
        }

    # Calculate downtime from incidents
    total_seconds = 86400.0
    downtime_seconds = 0.0
    for incident in incidents:
        inc_start = max(incident.started_at, day_start)
        inc_end = min(incident.ended_at or timezone.now(), day_end)
        downtime_seconds += max(0.0, (inc_end - inc_start).total_seconds())

    uptime_pct = round(((total_seconds - downtime_seconds) / total_seconds) * 100, 2)
    uptime_pct = max(0.0, min(100.0, uptime_pct))

    return {
        "uptime_pct": uptime_pct,
        "total": 0,
        "success": 0,
        "failed": 0,
        "has_data": True,
    }


def get_hourly_availability(check: Check, hours: int = 24) -> list[dict]:
    """Return per-hour availability for the last N hours from CheckResult records.

    Each entry: {hour_start, hour_end, uptime_pct, total, failures}
    """
    now = timezone.now()
    result: list[dict] = []

    for i in range(hours - 1, -1, -1):
        hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=i)
        hour_end = hour_start + timedelta(hours=1)

        qs = check.results.filter(timestamp__gte=hour_start, timestamp__lt=hour_end)
        total = qs.count()
        failures = qs.filter(is_success=False).count() if total else 0
        uptime_pct = round(((total - failures) / total) * 100, 2) if total > 0 else 100.0

        result.append({
            "hour_start": hour_start,
            "hour_end": hour_end,
            "uptime_pct": uptime_pct,
            "total": total,
            "failures": failures,
        })

    return result


def get_monthly_availability(check: Check, year: int, month: int) -> dict:
    """Monthly uptime from Incident records.

    Returns: {uptime_pct, incidents, downtime_seconds, has_data}
    """
    from django.db.models import Q

    # Build month boundaries
    month_start = timezone.make_aware(datetime(year, month, 1))
    if month == 12:
        month_end = timezone.make_aware(datetime(year + 1, 1, 1))
    else:
        month_end = timezone.make_aware(datetime(year, month + 1, 1))

    total_seconds = (month_end - month_start).total_seconds()

    incidents = check.incidents.filter(
        started_at__lt=month_end,
    ).filter(
        Q(ended_at__gt=month_start) | Q(ended_at__isnull=True)
    )

    incident_count = incidents.count()
    downtime_seconds = 0.0

    for incident in incidents:
        inc_start = max(incident.started_at, month_start)
        inc_end = min(incident.ended_at or timezone.now(), month_end)
        downtime_seconds += max(0.0, (inc_end - inc_start).total_seconds())

    uptime_pct = round(((total_seconds - downtime_seconds) / total_seconds) * 100, 2) if total_seconds > 0 else 100.0
    uptime_pct = max(0.0, min(100.0, uptime_pct))

    has_data = incident_count > 0 or check.results.filter(
        timestamp__gte=month_start, timestamp__lt=month_end
    ).exists()

    return {
        "uptime_pct": uptime_pct,
        "incidents": incident_count,
        "downtime_seconds": downtime_seconds,
        "has_data": has_data,
    }


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------


def get_check_status(check: Check) -> str:
    """Return current status: 'down', 'paused', 'unknown', or 'up'."""
    if not check.is_active:
        return "paused"
    if check.incidents.filter(ended_at__isnull=True).exists():
        return "down"
    if not check.results.exists():
        return "unknown"
    return "up"


def get_uptime_color(downtime_pct: float) -> str:
    """Return a Tailwind CSS color class based on downtime percentage thresholds."""
    green = getattr(settings, "THRESHOLD_GREEN", 0.1)
    yellow = getattr(settings, "THRESHOLD_YELLOW", 1.0)
    orange = getattr(settings, "THRESHOLD_ORANGE", 5.0)

    if downtime_pct <= green:
        return "bg-green-500"
    elif downtime_pct <= yellow:
        return "bg-yellow-500"
    elif downtime_pct <= orange:
        return "bg-orange-500"
    else:
        return "bg-red-500"
