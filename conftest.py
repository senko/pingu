import pytest
from django.contrib.auth import get_user_model

from pingu.core.models import Check, CheckResult, Incident

User = get_user_model()


@pytest.fixture
def user(db):
    """Create and return a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def check(db, user):
    """Create and return a sample Check."""
    return Check.objects.create(
        name="Example Check",
        url="https://example.com",
        method="GET",
        expected_statuses=[200],
        timeout=10,
        interval=1,
        is_active=True,
        alert_enabled=True,
        alert_threshold=2,
        alert_email="alerts@example.com",
        created_by=user,
    )


@pytest.fixture
def check_no_alert(db, user):
    """Create a check with alerts disabled."""
    return Check.objects.create(
        name="Silent Check",
        url="https://example.com/silent",
        method="GET",
        expected_statuses=[200],
        timeout=5,
        interval=5,
        is_active=True,
        alert_enabled=False,
        created_by=user,
    )


@pytest.fixture
def success_result(db, check):
    """Create and return a successful CheckResult."""
    from decimal import Decimal

    from django.utils import timezone

    return CheckResult.objects.create(
        check=check,
        timestamp=timezone.now(),
        status_code=200,
        response_time=Decimal("0.150"),
        is_success=True,
    )


@pytest.fixture
def failure_result(db, check):
    """Create and return a failed CheckResult."""
    from django.utils import timezone

    return CheckResult.objects.create(
        check=check,
        timestamp=timezone.now(),
        status_code=500,
        response_time=None,
        is_success=False,
        error_message="Internal Server Error",
    )


@pytest.fixture
def open_incident(db, check):
    """Create and return an open Incident."""
    from django.utils import timezone

    return Incident.objects.create(
        check=check,
        started_at=timezone.now(),
    )


@pytest.fixture
def closed_incident(db, check):
    """Create and return a closed Incident."""
    from datetime import timedelta

    from django.utils import timezone

    started = timezone.now() - timedelta(hours=1)
    return Incident.objects.create(
        check=check,
        started_at=started,
        ended_at=timezone.now(),
    )
