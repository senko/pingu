from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Check(models.Model):
    HTTP_METHOD_CHOICES = [
        ("GET", "GET"),
        ("POST", "POST"),
        ("PUT", "PUT"),
        ("PATCH", "PATCH"),
        ("DELETE", "DELETE"),
        ("HEAD", "HEAD"),
        ("OPTIONS", "OPTIONS"),
    ]

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    url = models.URLField(max_length=2048)
    method = models.CharField(max_length=7, default="GET", choices=HTTP_METHOD_CHOICES)
    headers = models.JSONField(default=dict, blank=True)
    body = models.TextField(blank=True, default="")
    expected_statuses = models.JSONField(default=list, blank=True)
    timeout = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
    )
    interval = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
    )
    is_active = models.BooleanField(default=True)
    alert_enabled = models.BooleanField(default=True)
    alert_threshold = models.PositiveIntegerField(
        default=2,
        validators=[MinValueValidator(1)],
    )
    alert_email = models.EmailField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class CheckResult(models.Model):
    id = models.AutoField(primary_key=True)
    check = models.ForeignKey(  # type: ignore[assignment]
        Check, on_delete=models.CASCADE, related_name="results"
    )
    timestamp = models.DateTimeField(db_index=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    response_time = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    is_success = models.BooleanField()
    error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["check", "timestamp"]),
        ]

    def __str__(self) -> str:
        status = "OK" if self.is_success else "FAIL"
        return f"{self.check.name} @ {self.timestamp:%Y-%m-%d %H:%M} — {status}"


class Incident(models.Model):
    id = models.AutoField(primary_key=True)
    check = models.ForeignKey(  # type: ignore[assignment]
        Check, on_delete=models.CASCADE, related_name="incidents"
    )
    started_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    threshold_result = models.ForeignKey(
        CheckResult, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        state = "OPEN" if self.is_open else "CLOSED"
        return f"Incident for {self.check.name} ({state}) — started {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def is_open(self) -> bool:
        return self.ended_at is None

    @property
    def duration(self) -> timedelta:
        end = self.ended_at if self.ended_at else timezone.now()
        return end - self.started_at
