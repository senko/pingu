from django.contrib import admin

from pingu.alerts.models import AlertLog


@admin.register(AlertLog)
class AlertLogAdmin(admin.ModelAdmin):
    list_display = ("check", "alert_type", "recipient", "sent_at", "success")
    list_filter = ("alert_type", "success")
    search_fields = ("check__name", "recipient")
    readonly_fields = ("sent_at",)
    raw_id_fields = ("check", "incident")
