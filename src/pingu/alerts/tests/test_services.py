from datetime import timedelta
from unittest.mock import patch

import pytest

from pingu.alerts.models import AlertLog
from pingu.alerts.services import (
    _format_duration,
    get_alert_recipient,
    send_down_alert,
    send_up_alert,
)

# -- get_alert_recipient -----------------------------------------------------


class TestGetAlertRecipient:
    def test_returns_alert_email_if_set(self, check):
        assert check.alert_email == "alerts@example.com"
        assert get_alert_recipient(check) == "alerts@example.com"

    def test_falls_back_to_created_by_email(self, check, user):
        check.alert_email = ""
        check.save()

        assert get_alert_recipient(check) == user.email

    def test_returns_none_if_neither_available(self, db):
        from pingu.core.models import Check

        check = Check.objects.create(
            name="Orphan Check",
            url="https://orphan.example.com",
            alert_email="",
            created_by=None,
        )
        assert get_alert_recipient(check) is None


# -- send_down_alert ---------------------------------------------------------


class TestSendDownAlert:
    def test_sends_email_and_creates_alert_log(self, check, open_incident, mailoutbox):
        send_down_alert(check, open_incident, consecutive_failures=3)

        assert len(mailoutbox) == 1
        msg = mailoutbox[0]
        assert msg.subject == f"[Pingu] DOWN: {check.name}"
        assert check.url in msg.body
        assert "Consecutive failures: 3" in msg.body

        log = AlertLog.objects.get()
        assert log.check == check
        assert log.incident == open_incident
        assert log.alert_type == "down"
        assert log.recipient == "alerts@example.com"
        assert log.success is True
        assert log.error == ""

    def test_no_recipient_logs_warning_and_skips(self, db, open_incident, mailoutbox):
        from pingu.core.models import Check

        check = Check.objects.create(
            name="No Recipient",
            url="https://example.com",
            alert_email="",
            created_by=None,
        )
        incident = open_incident
        # Re-assign incident to this check so FK is consistent
        incident.check = check
        incident.save()

        with patch("pingu.alerts.services.logger") as mock_logger:
            send_down_alert(check, incident, consecutive_failures=1)

        assert len(mailoutbox) == 0
        assert AlertLog.objects.count() == 0
        mock_logger.warning.assert_called_once()

    def test_email_failure_creates_log_with_success_false(self, check, open_incident, mailoutbox):
        with patch(
            "pingu.alerts.services.send_mail",
            side_effect=Exception("SMTP error"),
        ):
            send_down_alert(check, open_incident, consecutive_failures=2)

        log = AlertLog.objects.get()
        assert log.success is False
        assert "SMTP error" in log.error


# -- send_up_alert -----------------------------------------------------------


class TestSendUpAlert:
    def test_sends_email_and_creates_alert_log(self, check, closed_incident, mailoutbox):
        send_up_alert(check, closed_incident)

        assert len(mailoutbox) == 1
        msg = mailoutbox[0]
        assert msg.subject == f"[Pingu] UP: {check.name}"
        assert check.url in msg.body

        log = AlertLog.objects.get()
        assert log.alert_type == "up"
        assert log.success is True

    def test_includes_duration_in_body(self, check, closed_incident, mailoutbox):
        send_up_alert(check, closed_incident)

        msg = mailoutbox[0]
        assert "Outage duration: 1h" in msg.body

    def test_no_recipient_logs_warning_and_skips(self, db, closed_incident, mailoutbox):
        from pingu.core.models import Check

        check = Check.objects.create(
            name="No Recipient",
            url="https://example.com",
            alert_email="",
            created_by=None,
        )
        closed_incident.check = check
        closed_incident.save()

        with patch("pingu.alerts.services.logger") as mock_logger:
            send_up_alert(check, closed_incident)

        assert len(mailoutbox) == 0
        assert AlertLog.objects.count() == 0
        mock_logger.warning.assert_called_once()

    def test_email_failure_creates_log_with_success_false(self, check, closed_incident, mailoutbox):
        with patch(
            "pingu.alerts.services.send_mail",
            side_effect=Exception("Connection refused"),
        ):
            send_up_alert(check, closed_incident)

        log = AlertLog.objects.get()
        assert log.success is False
        assert "Connection refused" in log.error


# -- _format_duration --------------------------------------------------------


class TestFormatDuration:
    @pytest.mark.parametrize(
        "td, expected",
        [
            (timedelta(seconds=0), "0s"),
            (timedelta(seconds=45), "45s"),
            (timedelta(minutes=5), "5m"),
            (timedelta(minutes=5, seconds=30), "5m 30s"),
            (timedelta(hours=2), "2h"),
            (timedelta(hours=2, minutes=15), "2h 15m"),
            (timedelta(hours=1, minutes=0, seconds=1), "1h 1s"),
            (timedelta(days=1), "1d"),
            (timedelta(days=3, hours=4, minutes=5, seconds=6), "3d 4h 5m 6s"),
            (timedelta(seconds=-10), "0s"),
        ],
    )
    def test_format_duration(self, td, expected):
        assert _format_duration(td) == expected
