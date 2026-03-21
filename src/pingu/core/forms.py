import json

from django import forms

from pingu.core.models import Check


class CheckForm(forms.ModelForm):
    expected_statuses = forms.CharField(
        required=False,
        help_text="Comma-separated HTTP status codes considered successful (e.g. 200, 201, 204).",
    )

    class Meta:
        model = Check
        fields = [
            "name",
            "url",
            "method",
            "headers",
            "body",
            "expected_statuses",
            "timeout",
            "interval",
            "is_active",
            "alert_enabled",
            "alert_threshold",
            "alert_email",
        ]
        widgets = {
            "method": forms.HiddenInput(),
            "headers": forms.HiddenInput(),
            "body": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # For new checks, default expected_statuses display
        if not self.instance.pk:
            self.initial.setdefault("expected_statuses", "200, 201, 204")
            self.initial.setdefault("method", "GET")
        else:
            # Convert stored list to comma-separated string for display
            statuses = self.instance.expected_statuses
            if isinstance(statuses, list):
                self.initial["expected_statuses"] = ", ".join(str(s) for s in statuses)

    def clean_expected_statuses(self) -> list[int]:
        raw = self.cleaned_data.get("expected_statuses", "")
        if not raw or not raw.strip():
            return [200, 201, 204]
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        statuses: list[int] = []
        for part in parts:
            try:
                code = int(part)
            except ValueError:
                raise forms.ValidationError(f"'{part}' is not a valid integer status code.")
            if code < 100 or code > 599:
                raise forms.ValidationError(f"Status code {code} is outside the valid HTTP range (100–599).")
            statuses.append(code)
        return statuses

    def clean_headers(self) -> dict:
        raw = self.cleaned_data.get("headers", "")
        if not raw or (isinstance(raw, str) and not raw.strip()):
            return {}
        if isinstance(raw, dict):
            return raw
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            raise forms.ValidationError("Headers must be valid JSON.")
        if not isinstance(parsed, dict):
            raise forms.ValidationError("Headers must be a JSON object (key/value pairs).")
        return parsed

    def clean_timeout(self) -> int:
        timeout = self.cleaned_data.get("timeout")
        if timeout is not None and (timeout < 1 or timeout > 30):
            raise forms.ValidationError("Timeout must be between 1 and 30 seconds.")
        return timeout

    def clean_interval(self) -> int:
        interval = self.cleaned_data.get("interval")
        if interval is not None and (interval < 1 or interval > 60):
            raise forms.ValidationError("Interval must be between 1 and 60 minutes.")
        return interval

    def clean_alert_threshold(self) -> int:
        threshold = self.cleaned_data.get("alert_threshold")
        if threshold is not None and threshold < 1:
            raise forms.ValidationError("Alert threshold must be at least 1.")
        return threshold
