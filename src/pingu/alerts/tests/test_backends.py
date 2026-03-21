from unittest.mock import patch

from pingu.alerts.backends import notify_down, notify_up


class TestNotifyDown:
    def test_delegates_to_send_down_alert(self, check, open_incident):
        with patch("pingu.alerts.backends.send_down_alert") as mock_send:
            notify_down(check, open_incident, consecutive_failures=3)

        mock_send.assert_called_once_with(check, open_incident, 3)


class TestNotifyUp:
    def test_delegates_to_send_up_alert(self, check, closed_incident):
        with patch("pingu.alerts.backends.send_up_alert") as mock_send:
            notify_up(check, closed_incident)

        mock_send.assert_called_once_with(check, closed_incident)
