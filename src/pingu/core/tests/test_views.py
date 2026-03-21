from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from pingu.core.models import Check, CheckResult

# ---------------------------------------------------------------------------
# Authentication enforcement
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuthenticationRequired:
    """All views should redirect unauthenticated users to the login page."""

    def test_dashboard_requires_login(self, client):
        resp = client.get(reverse("core:dashboard"))
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url

    def test_check_create_requires_login(self, client):
        resp = client.get(reverse("core:check_create"))
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url

    def test_check_detail_requires_login(self, client, check):
        resp = client.get(reverse("core:check_detail", args=[check.pk]))
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url

    def test_check_edit_requires_login(self, client, check):
        resp = client.get(reverse("core:check_edit", args=[check.pk]))
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url

    def test_check_delete_requires_login(self, client, check):
        resp = client.get(reverse("core:check_delete", args=[check.pk]))
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url

    def test_check_history_requires_login(self, client, check):
        resp = client.get(reverse("core:check_history", args=[check.pk]))
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url

    def test_check_run_requires_login(self, client, check):
        resp = client.post(reverse("core:check_run", args=[check.pk]))
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url


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

    def test_check_edit_404(self, client, user):
        client.force_login(user)
        resp = client.get(reverse("core:check_edit", args=[99999]))
        assert resp.status_code == 404


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

    def test_check_delete_404(self, client, user):
        client.force_login(user)
        resp = client.post(reverse("core:check_delete", args=[99999]))
        assert resp.status_code == 404


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

    def test_check_detail_404(self, client, user):
        client.force_login(user)
        resp = client.get(reverse("core:check_detail", args=[99999]))
        assert resp.status_code == 404


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
        client.force_login(user)
        resp = client.get(reverse("core:check_history", args=[check.pk]), {"status": "failed"})
        assert resp.status_code == 200
        assert resp.context["status_filter"] == "failed"

    def test_check_history_status_filter_success(self, client, user, check):
        client.force_login(user)
        resp = client.get(reverse("core:check_history", args=[check.pk]), {"status": "success"})
        assert resp.status_code == 200
        assert resp.context["status_filter"] == "success"

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

    def test_check_run_requires_post(self, client, user, check):
        client.force_login(user)
        resp = client.get(reverse("core:check_run", args=[check.pk]))
        assert resp.status_code == 405

    @patch("pingu.core.views.run_single_check")
    def test_check_run_404(self, mock_run, client, user):
        client.force_login(user)
        resp = client.post(reverse("core:check_run", args=[99999]))
        assert resp.status_code == 404
        mock_run.assert_not_called()
