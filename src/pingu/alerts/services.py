from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from pingu.alerts.models import AlertLog
from pingu.core.models import Check, Incident

logger = logging.getLogger(__name__)


def _format_duration(td: timedelta) -> str:
    """Return a human-readable duration string."""
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return "0s"
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def get_alert_recipient(check: Check) -> str | None:
    """Return the best email address to send alerts to, or None."""
    if check.alert_email:
        return check.alert_email
    if check.created_by and check.created_by.email:
        return check.created_by.email
    return None


def send_down_alert(check: Check, incident: Incident, consecutive_failures: int) -> None:
    """Send a DOWN alert email and log it."""
    recipient = get_alert_recipient(check)
    if not recipient:
        logger.warning("No alert recipient for check %s (id=%d)", check.name, check.pk)
        return

    # Get the last result for context
    last_result = check.results.order_by("-timestamp").first()
    last_status = "N/A"
    last_error = ""
    if last_result:
        if last_result.status_code is not None:
            last_status = str(last_result.status_code)
        if last_result.error_message:
            last_error = last_result.error_message

    now = timezone.now()
    subject = f"[Pingu] DOWN: {check.name}"
    body_lines = [
        f"Check: {check.name}",
        f"URL: {check.url}",
        f"Consecutive failures: {consecutive_failures}",
        f"Last response code: {last_status}",
    ]
    if last_error:
        body_lines.append(f"Error: {last_error}")
    body_lines.append(f"Timestamp: {now:%Y-%m-%d %H:%M:%S UTC}")
    body = "\n".join(body_lines)

    success = True
    error = ""
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception as exc:
        success = False
        error = str(exc)
        logger.exception("Failed to send DOWN alert for check %s", check.name)

    AlertLog.objects.create(
        check=check,
        incident=incident,
        alert_type="down",
        recipient=recipient,
        success=success,
        error=error,
    )


def send_up_alert(check: Check, incident: Incident) -> None:
    """Send an UP (recovery) alert email and log it."""
    recipient = get_alert_recipient(check)
    if not recipient:
        logger.warning("No alert recipient for check %s (id=%d)", check.name, check.pk)
        return

    duration = incident.duration
    now = timezone.now()
    subject = f"[Pingu] UP: {check.name}"
    body = (
        f"Check: {check.name}\n"
        f"URL: {check.url}\n"
        f"Outage duration: {_format_duration(duration)}\n"
        f"Recovery timestamp: {now:%Y-%m-%d %H:%M:%S UTC}"
    )

    success = True
    error = ""
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception as exc:
        success = False
        error = str(exc)
        logger.exception("Failed to send UP alert for check %s", check.name)

    AlertLog.objects.create(
        check=check,
        incident=incident,
        alert_type="up",
        recipient=recipient,
        success=success,
        error=error,
    )
