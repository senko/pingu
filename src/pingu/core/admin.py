from django.contrib import admin

from pingu.core.models import Check, CheckResult, Incident


@admin.register(Check)
class CheckAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "method", "interval", "is_active", "alert_enabled", "created_at")
    list_filter = ("is_active", "alert_enabled", "method")
    search_fields = ("name", "url")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CheckResult)
class CheckResultAdmin(admin.ModelAdmin):
    list_display = ("check", "timestamp", "status_code", "response_time", "is_success")
    list_filter = ("is_success",)
    search_fields = ("check__name",)
    readonly_fields = ("timestamp",)
    raw_id_fields = ("check",)


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("check", "started_at", "ended_at", "is_open")
    list_filter = ("ended_at",)
    search_fields = ("check__name",)
    raw_id_fields = ("check", "threshold_result")

    @admin.display(boolean=True, description="Open?")
    def is_open(self, obj: Incident) -> bool:
        return obj.is_open
