from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from django.db import models
from django.db.models import Manager

from pingu.core.models import Check, Incident


class AlertLog(models.Model):
    ALERT_TYPE_CHOICES = [
        ("down", "Down"),
        ("up", "Up"),
    ]

    check = models.ForeignKey(Check, on_delete=models.CASCADE, related_name="alert_logs")
    incident = models.ForeignKey(Incident, on_delete=models.SET_NULL, null=True, blank=True, related_name="alert_logs")
    alert_type = models.CharField(max_length=4, choices=ALERT_TYPE_CHOICES)
    recipient = models.EmailField()
    sent_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    error = models.TextField(blank=True, default="")

    if TYPE_CHECKING:
        objects: Manager[AlertLog]
        id: int
        check: Check  # type: ignore[assignment]
        check_id: int
        incident: Incident | None  # type: ignore[assignment]
        incident_id: int | None
        alert_type: str  # type: ignore[assignment]
        recipient: str  # type: ignore[assignment]
        sent_at: datetime  # type: ignore[assignment]
        success: bool  # type: ignore[assignment]
        error: str  # type: ignore[assignment]

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self) -> str:
        return f"{self.alert_type.upper()} alert for {self.check.name} -> {self.recipient}"
