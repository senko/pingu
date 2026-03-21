from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from pingu.alerts.models import AlertLog
from pingu.core.models import Check, CheckResult, Incident

User = get_user_model()


# ── Check model ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCheck:
    def test_str(self, check):
        assert str(check) == "Example Check"

    def test_defaults(self, db):
        c = Check.objects.create(name="Minimal", url="https://example.com")
        assert c.method == "GET"
        assert c.headers == {}
        assert c.body == ""
        assert c.expected_statuses == []
        assert c.timeout == 10
        assert c.interval == 1
        assert c.is_active is True
        assert c.alert_enabled is True
        assert c.alert_threshold == 2
        assert c.alert_email == ""
        assert c.created_by is None

    def test_ordering(self, db, user):
        Check.objects.create(name="Zebra", url="https://z.com", created_by=user)
        Check.objects.create(name="Alpha", url="https://a.com", created_by=user)
        names = list(Check.objects.values_list("name", flat=True))
        assert names == ["Alpha", "Zebra"]

    def test_created_by_set_null_on_user_delete(self, check, user):
        user.delete()
        check.refresh_from_db()
        assert check.created_by is None

    def test_auto_timestamps(self, check):
        assert check.created_at is not None
        assert check.updated_at is not None


# ── CheckResult model ────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCheckResult:
    def test_str_success(self, success_result):
        assert "OK" in str(success_result)
        assert "Example Check" in str(success_result)

    def test_str_failure(self, failure_result):
        assert "FAIL" in str(failure_result)

    def test_ordering(self, check):
        now = timezone.now()
        older = CheckResult.objects.create(check=check, timestamp=now - timedelta(hours=1), is_success=True)
        newer = CheckResult.objects.create(check=check, timestamp=now, is_success=True)
        results = list(CheckResult.objects.filter(check=check))
        assert results[0] == newer
        assert results[1] == older

    def test_nullable_fields(self, check):
        result = CheckResult.objects.create(
            check=check,
            timestamp=timezone.now(),
            is_success=False,
            status_code=None,
            response_time=None,
        )
        result.refresh_from_db()
        assert result.status_code is None
        assert result.response_time is None

    def test_cascade_on_check_delete(self, success_result):
        check_id = success_result.check_id
        Check.objects.filter(pk=check_id).delete()
        assert not CheckResult.objects.filter(pk=success_result.pk).exists()


# ── Incident model ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestIncident:
    def test_str_open(self, open_incident):
        s = str(open_incident)
        assert "OPEN" in s
        assert "Example Check" in s

    def test_str_closed(self, closed_incident):
        assert "CLOSED" in str(closed_incident)

    def test_is_open_true(self, open_incident):
        assert open_incident.is_open is True

    def test_is_open_false(self, closed_incident):
        assert closed_incident.is_open is False

    def test_duration_open_incident(self, check):
        started = timezone.now() - timedelta(minutes=30)
        incident = Incident.objects.create(check=check, started_at=started)
        duration = incident.duration
        assert timedelta(minutes=29) < duration < timedelta(minutes=31)

    def test_duration_closed_incident(self, check):
        started = timezone.now() - timedelta(hours=2)
        ended = started + timedelta(hours=1)
        incident = Incident.objects.create(check=check, started_at=started, ended_at=ended)
        assert incident.duration == timedelta(hours=1)

    def test_threshold_result_set_null_on_result_delete(self, check, success_result):
        incident = Incident.objects.create(
            check=check,
            started_at=timezone.now(),
            threshold_result=success_result,
        )
        success_result.delete()
        incident.refresh_from_db()
        assert incident.threshold_result is None

    def test_cascade_on_check_delete(self, open_incident):
        check_id = open_incident.check_id
        Check.objects.filter(pk=check_id).delete()
        assert not Incident.objects.filter(pk=open_incident.pk).exists()

    def test_ordering(self, check):
        now = timezone.now()
        older = Incident.objects.create(check=check, started_at=now - timedelta(hours=1))
        newer = Incident.objects.create(check=check, started_at=now)
        incidents = list(Incident.objects.filter(check=check))
        assert incidents[0] == newer
        assert incidents[1] == older


# ── AlertLog model ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAlertLog:
    def test_str(self, check):
        log = AlertLog.objects.create(
            check=check,
            alert_type="down",
            recipient="ops@example.com",
        )
        s = str(log)
        assert "DOWN" in s
        assert "Example Check" in s
        assert "ops@example.com" in s

    def test_defaults(self, check):
        log = AlertLog.objects.create(
            check=check,
            alert_type="up",
            recipient="ops@example.com",
        )
        assert log.success is True
        assert log.error == ""
        assert log.incident is None

    def test_cascade_on_check_delete(self, check):
        log = AlertLog.objects.create(check=check, alert_type="down", recipient="a@b.com")
        Check.objects.filter(pk=check.pk).delete()
        assert not AlertLog.objects.filter(pk=log.pk).exists()

    def test_incident_set_null_on_incident_delete(self, check, open_incident):
        log = AlertLog.objects.create(
            check=check,
            incident=open_incident,
            alert_type="down",
            recipient="a@b.com",
        )
        open_incident.delete()
        log.refresh_from_db()
        assert log.incident is None
