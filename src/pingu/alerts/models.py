from django.db import models

from pingu.core.models import Check, Incident


class AlertLog(models.Model):
    ALERT_TYPE_CHOICES = [
        ("down", "Down"),
        ("up", "Up"),
    ]

    check = models.ForeignKey(  # type: ignore[assignment]
        Check, on_delete=models.CASCADE, related_name="alert_logs"
    )
    incident = models.ForeignKey(
        Incident, on_delete=models.SET_NULL, null=True, blank=True, related_name="alert_logs"
    )
    alert_type = models.CharField(max_length=4, choices=ALERT_TYPE_CHOICES)
    recipient = models.EmailField()
    sent_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self) -> str:
        return f"{self.alert_type.upper()} alert for {self.check.name} -> {self.recipient}"
