from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import AsyncMock, patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from pingu.core.models import Check, CheckResult


@pytest.fixture
def check(db):
    return Check.objects.create(
        name="CMD Check",
        url="https://example.com",
        method="GET",
        expected_statuses=[200],
        timeout=10,
        interval=1,
        is_active=True,
    )


class TestRunChecks:
    @pytest.mark.django_db
    def test_no_checks_due(self):
        out = StringIO()
        with patch("pingu.core.management.commands.run_checks.get_checks_due", return_value=[]):
            call_command("run_checks", stdout=out)
        assert "No checks due" in out.getvalue()

    @pytest.mark.django_db
    def test_runs_due_checks_and_saves_results(self, check):
        mock_result = CheckResult(
            check=check,
            timestamp=timezone.now(),
            status_code=200,
            response_time=Decimal("0.123"),
            is_success=True,
        )

        out = StringIO()
        with (
            patch("pingu.core.management.commands.run_checks.get_checks_due", return_value=[check]),
            patch(
                "pingu.core.management.commands.run_checks.execute_checks",
                new_callable=AsyncMock,
                return_value=[mock_result],
            ),
            patch("pingu.core.management.commands.run_checks.evaluate_check_result") as mock_eval,
        ):
            call_command("run_checks", stdout=out)

        output = out.getvalue()
        assert "Running 1 check(s)" in output
        assert "1/1 results saved" in output

        # Result should have been saved to DB
        assert CheckResult.objects.filter(check=check).exists()
        mock_eval.assert_called_once_with(mock_result)


class TestCleanupResults:
    @pytest.mark.django_db
    def test_deletes_old_results_keeps_recent(self, check):
        old = CheckResult.objects.create(
            check=check,
            timestamp=timezone.now() - timedelta(days=10),
            status_code=200,
            response_time=Decimal("0.100"),
            is_success=True,
        )
        recent = CheckResult.objects.create(
            check=check,
            timestamp=timezone.now() - timedelta(days=1),
            status_code=200,
            response_time=Decimal("0.100"),
            is_success=True,
        )

        out = StringIO()
        call_command("cleanup_results", stdout=out)

        assert not CheckResult.objects.filter(pk=old.pk).exists()
        assert CheckResult.objects.filter(pk=recent.pk).exists()
        assert "Deleted 1 result(s)" in out.getvalue()

    @pytest.mark.django_db
    def test_days_override(self, check):
        result = CheckResult.objects.create(
            check=check,
            timestamp=timezone.now() - timedelta(days=3),
            status_code=200,
            response_time=Decimal("0.100"),
            is_success=True,
        )

        out = StringIO()
        call_command("cleanup_results", "--days=2", stdout=out)

        assert not CheckResult.objects.filter(pk=result.pk).exists()
        assert "Deleted 1 result(s) older than 2 day(s)" in out.getvalue()

    @pytest.mark.django_db
    def test_no_stale_results(self, check):
        CheckResult.objects.create(
            check=check,
            timestamp=timezone.now(),
            status_code=200,
            response_time=Decimal("0.100"),
            is_success=True,
        )

        out = StringIO()
        call_command("cleanup_results", stdout=out)

        assert "No stale results to clean up" in out.getvalue()
        assert CheckResult.objects.count() == 1
