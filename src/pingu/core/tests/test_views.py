from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from pingu.core.models import Check, CheckResult

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDashboard:
    def test_dashboard_authenticated(self, client, user, check):
        client.force_login(user)
        resp = client.get(reverse("core:dashboard"))
        assert resp.status_code == 200
        assert "check_data" in resp.context
        assert resp.context["total"] == 1

    def test_dashboard_empty(self, client, user):
        client.force_login(user)
        resp = client.get(reverse("core:dashboard"))
        assert resp.status_code == 200
        assert resp.context["total"] == 0


# ---------------------------------------------------------------------------
# Check Create
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCheckCreate:
    def test_check_create_get(self, client, user):
        client.force_login(user)
        resp = client.get(reverse("core:check_create"))
        assert resp.status_code == 200
        assert "form" in resp.context
        assert resp.context["is_edit"] is False

    def test_check_create_post(self, client, user):
        client.force_login(user)
        data = {
            "name": "New Check",
            "url": "https://httpbin.org/get",
            "method": "GET",
            "expected_statuses": "200, 201",
            "timeout": 10,
            "interval": 5,
            "is_active": True,
            "alert_enabled": True,
            "alert_threshold": 2,
            "alert_email": "test@example.com",
        }
        resp = client.post(reverse("core:check_create"), data)
        assert resp.status_code == 302
        new_check = Check.objects.get(name="New Check")
        assert new_check.created_by == user
        assert new_check.expected_statuses == [200, 201]
        assert resp.url == reverse("core:check_detail", args=[new_check.pk])

    def test_check_create_post_invalid(self, client, user):
        client.force_login(user)
        data = {"name": "", "url": ""}
        resp = client.post(reverse("core:check_create"), data)
        assert resp.status_code == 200
        assert resp.context["form"].errors


# ---------------------------------------------------------------------------
# Check Edit
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCheckEdit:
    def test_check_edit_get(self, client, user, check):
        client.force_login(user)
        resp = client.get(reverse("core:check_edit", args=[check.pk]))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is True
        assert resp.context["form"].instance == check

    def test_check_edit_post(self, client, user, check):
        client.force_login(user)
        data = {
            "name": "Updated Check",
            "url": check.url,
            "method": "GET",
            "expected_statuses": "200",
            "timeout": 15,
            "interval": 2,
            "is_active": True,
            "alert_enabled": False,
            "alert_threshold": 3,
            "alert_email": "",
        }
        resp = client.post(reverse("core:check_edit", args=[check.pk]), data)
        assert resp.status_code == 302
        check.refresh_from_db()
        assert check.name == "Updated Check"
        assert check.timeout == 15


# ---------------------------------------------------------------------------
# Check Delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCheckDelete:
    def test_check_delete_get(self, client, user, check):
        client.force_login(user)
        resp = client.get(reverse("core:check_delete", args=[check.pk]))
        assert resp.status_code == 200
        assert resp.context["check"] == check

    def test_check_delete_post(self, client, user, check):
        client.force_login(user)
        pk = check.pk
        resp = client.post(reverse("core:check_delete", args=[pk]))
        assert resp.status_code == 302
        assert resp.url == reverse("core:dashboard")
        assert not Check.objects.filter(pk=pk).exists()


# ---------------------------------------------------------------------------
# Check Detail
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCheckDetail:
    def test_check_detail(self, client, user, check):
        client.force_login(user)
        resp = client.get(reverse("core:check_detail", args=[check.pk]))
        assert resp.status_code == 200
        assert resp.context["check"] == check
        assert "status" in resp.context
        assert "hourly_data" in resp.context
        assert "daily_data" in resp.context


# ---------------------------------------------------------------------------
# Check History
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCheckHistory:
    def test_check_history_default(self, client, user, check):
        client.force_login(user)
        resp = client.get(reverse("core:check_history", args=[check.pk]))
        assert resp.status_code == 200
        assert resp.context["day_offset"] == 0
        assert resp.context["status_filter"] == "all"

    def test_check_history_day_param(self, client, user, check):
        client.force_login(user)
        resp = client.get(reverse("core:check_history", args=[check.pk]), {"day": "2"})
        assert resp.status_code == 200
        assert resp.context["day_offset"] == 2

    def test_check_history_day_clamped(self, client, user, check):
        client.force_login(user)
        # Day offset larger than max should be clamped
        resp = client.get(reverse("core:check_history", args=[check.pk]), {"day": "9999"})
        assert resp.status_code == 200
        assert resp.context["day_offset"] <= resp.context["max_day"]

    def test_check_history_day_negative_clamped(self, client, user, check):
        client.force_login(user)
        resp = client.get(reverse("core:check_history", args=[check.pk]), {"day": "-5"})
        assert resp.status_code == 200
        assert resp.context["day_offset"] == 0

    def test_check_history_day_invalid(self, client, user, check):
        client.force_login(user)
        resp = client.get(reverse("core:check_history", args=[check.pk]), {"day": "abc"})
        assert resp.status_code == 200
        assert resp.context["day_offset"] == 0

    def test_check_history_status_filter_failed(self, client, user, check):
        # Create both a success and failure result for today
        now = timezone.now()
        CheckResult.objects.create(check=check, timestamp=now, status_code=200, is_success=True)
        CheckResult.objects.create(check=check, timestamp=now, status_code=500, is_success=False)

        client.force_login(user)
        resp = client.get(reverse("core:check_history", args=[check.pk]), {"status": "failed"})
        assert resp.status_code == 200
        assert resp.context["status_filter"] == "failed"
        results = list(resp.context["results"])
        assert len(results) == 1
        assert results[0].is_success is False

    def test_check_history_status_filter_success(self, client, user, check):
        now = timezone.now()
        CheckResult.objects.create(check=check, timestamp=now, status_code=200, is_success=True)
        CheckResult.objects.create(check=check, timestamp=now, status_code=500, is_success=False)

        client.force_login(user)
        resp = client.get(reverse("core:check_history", args=[check.pk]), {"status": "success"})
        assert resp.status_code == 200
        assert resp.context["status_filter"] == "success"
        results = list(resp.context["results"])
        assert len(results) == 1
        assert results[0].is_success is True

    def test_check_history_status_filter_invalid(self, client, user, check):
        client.force_login(user)
        resp = client.get(reverse("core:check_history", args=[check.pk]), {"status": "bogus"})
        assert resp.status_code == 200
        assert resp.context["status_filter"] == "all"

    def test_check_history_pagination_links(self, client, user, check):
        client.force_login(user)
        # Day 0 (today) should have no next_day, but should have prev_day
        resp = client.get(reverse("core:check_history", args=[check.pk]))
        assert resp.context["next_day"] is None
        assert resp.context["prev_day"] == 1

    def test_check_history_with_results(self, client, user, check, success_result):
        client.force_login(user)
        resp = client.get(reverse("core:check_history", args=[check.pk]))
        assert resp.status_code == 200
        assert resp.context["summary"]["total"] >= 1


# ---------------------------------------------------------------------------
# Check Run
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCheckRun:
    @patch("pingu.core.views.run_single_check")
    def test_check_run_success(self, mock_run, client, user, check):
        mock_result = CheckResult(
            check=check,
            timestamp=timezone.now(),
            status_code=200,
            response_time=Decimal("0.123"),
            is_success=True,
        )
        mock_run.return_value = mock_result

        client.force_login(user)
        resp = client.post(reverse("core:check_run", args=[check.pk]))
        assert resp.status_code == 302
        assert resp.url == reverse("core:check_detail", args=[check.pk])
        mock_run.assert_called_once_with(check)

        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        assert len(msgs) == 1
        assert "200" in msgs[0]
        assert "0.123" in msgs[0]

    @patch("pingu.core.views.run_single_check")
    def test_check_run_failure(self, mock_run, client, user, check):
        mock_result = CheckResult(
            check=check,
            timestamp=timezone.now(),
            status_code=500,
            response_time=None,
            is_success=False,
            error_message="Internal Server Error",
        )
        mock_run.return_value = mock_result

        client.force_login(user)
        resp = client.post(reverse("core:check_run", args=[check.pk]))
        assert resp.status_code == 302
        assert resp.url == reverse("core:check_detail", args=[check.pk])
        mock_run.assert_called_once_with(check)

        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        assert len(msgs) == 1
        assert "failed" in msgs[0]
        assert "Internal Server Error" in msgs[0]

    def test_check_run_requires_post(self, client, user, check):
        client.force_login(user)
        resp = client.get(reverse("core:check_run", args=[check.pk]))
        assert resp.status_code == 405

