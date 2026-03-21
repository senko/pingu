from __future__ import annotations

from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from pingu.core.forms import CheckForm
from pingu.core.models import Check, CheckResult, Incident
from pingu.core.services import (
    get_check_status,
    get_daily_availability,
    get_hourly_availability,
    get_monthly_availability,
    run_single_check,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _relative_time(dt: datetime | None) -> str:
    """Return a human-friendly relative time string like '47s ago'."""
    if dt is None:
        return "never"
    now = timezone.now()
    delta = now - dt
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        return "just now"
    if total_seconds < 60:
        return f"{total_seconds}s ago"
    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _get_uptime_bar_color(uptime_pct: float | None) -> str:
    """Return a CSS status class based on uptime percentage.

    Uses the downtime thresholds from settings:
    - THRESHOLD_GREEN  (default 0.1%) – anything above (100 - green) is green
    - THRESHOLD_YELLOW (default 1.0%)
    - THRESHOLD_ORANGE (default 5.0%)
    """
    if uptime_pct is None:
        return "surface-600"

    green = getattr(settings, "THRESHOLD_GREEN", 0.1)
    yellow = getattr(settings, "THRESHOLD_YELLOW", 1.0)
    orange = getattr(settings, "THRESHOLD_ORANGE", 5.0)

    downtime_pct = 100.0 - uptime_pct

    if downtime_pct <= green:
        return "status-up"
    if downtime_pct <= yellow:
        return "status-warn"
    if downtime_pct <= orange:
        return "status-orange"
    return "status-down"


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@login_required
def dashboard(request):
    checks = Check.objects.all()
    now = timezone.now()
    today = now.date()

    check_data = []
    up_count = 0
    down_count = 0
    paused_count = 0

    for check in checks:
        status = get_check_status(check)

        if status == "up":
            up_count += 1
        elif status == "down":
            down_count += 1
        elif status == "paused":
            paused_count += 1

        # Today's uptime
        daily = get_daily_availability(check, today)
        uptime_today = daily["uptime_pct"]

        # Hourly availability for uptime strip (last 24h)
        hourly_data = get_hourly_availability(check, hours=24)
        for entry in hourly_data:
            entry["color"] = (
                _get_uptime_bar_color(entry["uptime_pct"])
                if entry["total"] > 0
                else "surface-600"
            )

        # Last result
        last_result = check.results.order_by("-timestamp").first()
        if last_result:
            last_checked_ago = _relative_time(last_result.timestamp)
            last_status_code = last_result.status_code
        else:
            last_checked_ago = "never"
            last_status_code = None

        # Last status change info
        if status == "down":
            open_incident = check.incidents.filter(ended_at__isnull=True).first()
            if open_incident:
                last_status_change = f"Down since {open_incident.started_at:%Y-%m-%d %H:%M}"
            else:
                last_status_change = "Down"
        else:
            # Up, paused, or unknown – find most recent closed incident
            last_closed = check.incidents.filter(ended_at__isnull=False).order_by("-ended_at").first()
            if last_closed:
                last_status_change = f"Up since {last_closed.ended_at:%Y-%m-%d %H:%M}"
            else:
                last_status_change = f"Up since {check.created_at:%Y-%m-%d %H:%M}"

        check_data.append(
            {
                "check": check,
                "status": status,
                "uptime_today": uptime_today,
                "hourly_data": hourly_data,
                "last_result": last_result,
                "last_checked_ago": last_checked_ago,
                "last_status_code": last_status_code,
                "last_status_change": last_status_change,
            }
        )

    # Compute last_run_ago across all checks
    latest_result = CheckResult.objects.order_by("-timestamp").first()
    last_run_ago = _relative_time(latest_result.timestamp) if latest_result else "never"

    context = {
        "check_data": check_data,
        "total": checks.count(),
        "up_count": up_count,
        "down_count": down_count,
        "paused_count": paused_count,
        "last_run_ago": last_run_ago,
    }
    return render(request, "core/dashboard.html", context)


# ---------------------------------------------------------------------------
# Check CRUD
# ---------------------------------------------------------------------------


@login_required
def check_create(request):
    if request.method == "POST":
        form = CheckForm(request.POST)
        if form.is_valid():
            check = form.save(commit=False)
            check.created_by = request.user
            if not check.expected_statuses:
                check.expected_statuses = [200, 201, 204]
            check.save()
            messages.success(request, f'Check "{check.name}" created successfully.')
            return redirect("core:check_detail", pk=check.pk)
    else:
        form = CheckForm()

    return render(request, "core/check_form.html", {"form": form, "is_edit": False})


@login_required
def check_detail(request, pk):
    check = get_object_or_404(Check, pk=pk)
    now = timezone.now()
    today = now.date()

    status = get_check_status(check)

    # Hourly availability (last 24h)
    hourly_data = get_hourly_availability(check, hours=24)
    for entry in hourly_data:
        entry["color"] = (
            _get_uptime_bar_color(entry["uptime_pct"])
            if entry["total"] > 0
            else "surface-600"
        )

    # Daily availability (last 30 days)
    daily_data = []
    for i in range(29, -1, -1):
        target_date = today - timedelta(days=i)
        day_avail = get_daily_availability(check, target_date)
        day_avail["date"] = target_date
        day_avail["color"] = (
            _get_uptime_bar_color(day_avail["uptime_pct"])
            if day_avail["has_data"]
            else "surface-600"
        )
        daily_data.append(day_avail)

    # Monthly history (months older than 30 days where check existed)
    monthly_data = []
    check_created = check.created_at.date()
    boundary = today - timedelta(days=30)
    # Walk backwards from boundary month to check creation month
    current = date(boundary.year, boundary.month, 1)
    earliest = date(check_created.year, check_created.month, 1)
    while current >= earliest:
        month_avail = get_monthly_availability(check, current.year, current.month)
        month_avail["year"] = current.year
        month_avail["month"] = current.month
        month_avail["label"] = current.strftime("%B %Y")
        month_avail["color"] = (
            _get_uptime_bar_color(month_avail["uptime_pct"])
            if month_avail["has_data"]
            else "surface-600"
        )
        monthly_data.append(month_avail)
        # Go to previous month
        if current.month == 1:
            current = date(current.year - 1, 12, 1)
        else:
            current = date(current.year, current.month - 1, 1)

    # Recent incidents
    incidents = check.incidents.order_by("-started_at")[:10]

    # Uptime summaries
    uptime_24h_data = get_daily_availability(check, today)
    uptime_24h = uptime_24h_data["uptime_pct"]

    thirty_days_ago = today - timedelta(days=30)
    uptime_30d_total = 0
    uptime_30d_count = 0
    for i in range(30):
        d = today - timedelta(days=i)
        day_info = get_daily_availability(check, d)
        if day_info["has_data"] or day_info["total"] > 0:
            uptime_30d_total += day_info["uptime_pct"]
            uptime_30d_count += 1
    uptime_30d = round(uptime_30d_total / uptime_30d_count, 2) if uptime_30d_count > 0 else 100.0

    context = {
        "check": check,
        "status": status,
        "hourly_data": hourly_data,
        "daily_data": daily_data,
        "monthly_data": monthly_data,
        "incidents": incidents,
        "uptime_24h": uptime_24h,
        "uptime_30d": uptime_30d,
    }
    return render(request, "core/check_detail.html", context)


@login_required
def check_edit(request, pk):
    check = get_object_or_404(Check, pk=pk)

    if request.method == "POST":
        form = CheckForm(request.POST, instance=check)
        if form.is_valid():
            form.save()
            messages.success(request, f'Check "{check.name}" updated successfully.')
            return redirect("core:check_detail", pk=check.pk)
    else:
        form = CheckForm(instance=check)

    return render(
        request, "core/check_form.html", {"form": form, "is_edit": True, "check": check}
    )


@login_required
def check_delete(request, pk):
    check = get_object_or_404(Check, pk=pk)

    if request.method == "POST":
        name = check.name
        check.delete()
        messages.success(request, f'Check "{name}" deleted successfully.')
        return redirect("core:dashboard")

    return render(request, "core/check_confirm_delete.html", {"check": check})


# ---------------------------------------------------------------------------
# Check history
# ---------------------------------------------------------------------------


@login_required
def check_history(request, pk):
    check = get_object_or_404(Check, pk=pk)
    max_day = settings.RESULT_RETENTION_DAYS - 1

    # Day offset (0 = today)
    try:
        day_offset = int(request.GET.get("day", 0))
    except (TypeError, ValueError):
        day_offset = 0
    day_offset = max(0, min(day_offset, max_day))

    # Status filter
    status_filter = request.GET.get("status", "all")
    if status_filter not in ("all", "failed", "success"):
        status_filter = "all"

    # Target date
    today = timezone.now().date()
    target_date = today - timedelta(days=day_offset)
    day_start = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
    day_end = day_start + timedelta(days=1)

    # Query results for this day
    results = check.results.filter(timestamp__gte=day_start, timestamp__lt=day_end)

    if status_filter == "failed":
        results = results.filter(is_success=False)
    elif status_filter == "success":
        results = results.filter(is_success=True)

    results = results.order_by("-timestamp")

    # Day summary (computed from all results for the day, ignoring filter)
    all_day_results = check.results.filter(timestamp__gte=day_start, timestamp__lt=day_end)
    total = all_day_results.count()
    success = all_day_results.filter(is_success=True).count()
    failed = total - success
    uptime_pct = round((success / total) * 100, 2) if total > 0 else 100.0
    avg_response_time = all_day_results.filter(
        response_time__isnull=False
    ).aggregate(avg=Avg("response_time"))["avg"]

    summary = {
        "total": total,
        "success": success,
        "failed": failed,
        "uptime_pct": uptime_pct,
        "avg_response_time": round(avg_response_time, 3) if avg_response_time else None,
    }

    # Pagination
    prev_day = day_offset + 1 if day_offset < max_day else None
    next_day = day_offset - 1 if day_offset > 0 else None

    context = {
        "check": check,
        "results": results,
        "day_offset": day_offset,
        "target_date": target_date,
        "status_filter": status_filter,
        "summary": summary,
        "max_day": max_day,
        "prev_day": prev_day,
        "next_day": next_day,
    }
    return render(request, "core/check_history.html", context)


# ---------------------------------------------------------------------------
# Run check
# ---------------------------------------------------------------------------


@login_required
@require_POST
def check_run(request, pk):
    check = get_object_or_404(Check, pk=pk)
    result = run_single_check(check)

    if result.is_success:
        messages.success(
            request,
            f'"{check.name}" responded with {result.status_code} '
            f"in {result.response_time}s.",
        )
    else:
        error = result.error_message or f"HTTP {result.status_code}"
        messages.error(
            request,
            f'"{check.name}" check failed: {error}',
        )

    return redirect("core:check_detail", pk=check.pk)
