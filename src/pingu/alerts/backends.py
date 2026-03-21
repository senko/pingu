"""Thin alert backend abstraction.

Currently only email is supported.  This module exists so that additional
backends (Slack, webhooks, etc.) can be plugged in later without touching
the core alert-evaluation logic.
"""

from __future__ import annotations

from pingu.alerts.services import send_down_alert, send_up_alert
from pingu.core.models import Check, Incident


def notify_down(check: Check, incident: Incident, consecutive_failures: int) -> None:
    """Dispatch a DOWN notification via all configured backends."""
    send_down_alert(check, incident, consecutive_failures)


def notify_up(check: Check, incident: Incident) -> None:
    """Dispatch an UP notification via all configured backends."""
    send_up_alert(check, incident)
