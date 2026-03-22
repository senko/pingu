import pytest

from pingu.core.forms import CheckForm


def valid_form_data(**overrides):
    data = {
        "name": "Test Check",
        "url": "https://example.com",
        "method": "GET",
        "expected_statuses": "200, 201",
        "headers": "",
        "body": "",
        "timeout": 10,
        "interval": 5,
        "is_active": True,
        "alert_enabled": True,
        "alert_threshold": 2,
        "alert_email": "test@example.com",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
class TestCheckFormValid:
    def test_valid_data_produces_valid_form(self):
        form = CheckForm(data=valid_form_data())
        assert form.is_valid(), form.errors

    def test_valid_form_saves(self):
        form = CheckForm(data=valid_form_data())
        assert form.is_valid(), form.errors
        check = form.save()
        assert check.pk is not None
        assert check.name == "Test Check"


@pytest.mark.django_db
class TestURLValidation:
    def test_invalid_url_rejected(self):
        form = CheckForm(data=valid_form_data(url="not-a-url"))
        assert not form.is_valid()
        assert "url" in form.errors

    def test_valid_url_accepted(self):
        form = CheckForm(data=valid_form_data(url="https://example.com/path"))
        assert form.is_valid(), form.errors


@pytest.mark.django_db
class TestExpectedStatuses:
    def test_comma_separated_parsed_to_list(self):
        form = CheckForm(data=valid_form_data(expected_statuses="200, 301, 404"))
        assert form.is_valid(), form.errors
        assert form.cleaned_data["expected_statuses"] == [200, 301, 404]

    def test_single_status_parsed(self):
        form = CheckForm(data=valid_form_data(expected_statuses="200"))
        assert form.is_valid(), form.errors
        assert form.cleaned_data["expected_statuses"] == [200]

    def test_non_integer_rejected(self):
        form = CheckForm(data=valid_form_data(expected_statuses="200, abc"))
        assert not form.is_valid()
        assert "expected_statuses" in form.errors

    def test_status_code_zero_rejected(self):
        form = CheckForm(data=valid_form_data(expected_statuses="0"))
        assert not form.is_valid()
        assert "expected_statuses" in form.errors

    def test_status_code_600_rejected(self):
        form = CheckForm(data=valid_form_data(expected_statuses="600"))
        assert not form.is_valid()
        assert "expected_statuses" in form.errors

    def test_empty_defaults_to_standard_codes(self):
        form = CheckForm(data=valid_form_data(expected_statuses=""))
        assert form.is_valid(), form.errors
        assert form.cleaned_data["expected_statuses"] == [200, 201, 204]


@pytest.mark.django_db
class TestHeaders:
    def test_valid_json_accepted(self):
        form = CheckForm(data=valid_form_data(headers='{"Authorization": "Bearer tok"}'))
        assert form.is_valid(), form.errors
        assert form.cleaned_data["headers"] == {"Authorization": "Bearer tok"}

    def test_invalid_json_rejected(self):
        form = CheckForm(data=valid_form_data(headers="{not json}"))
        assert not form.is_valid()
        assert "headers" in form.errors

    def test_empty_headers_accepted(self):
        form = CheckForm(data=valid_form_data(headers=""))
        assert form.is_valid(), form.errors
        assert form.cleaned_data["headers"] == {}

    def test_dict_passthrough(self):
        form = CheckForm(data=valid_form_data(headers={"X-Custom": "value"}))
        assert form.is_valid(), form.errors
        assert form.cleaned_data["headers"] == {"X-Custom": "value"}

    def test_json_list_rejected(self):
        """A JSON list should be rejected — headers must be a dict (gap 6.4)."""
        form = CheckForm(data=valid_form_data(headers='["Content-Type"]'))
        assert not form.is_valid()
        assert "headers" in form.errors


@pytest.mark.django_db
class TestTimeout:
    def test_valid_timeout(self):
        form = CheckForm(data=valid_form_data(timeout=15))
        assert form.is_valid(), form.errors

    def test_timeout_below_min_rejected(self):
        form = CheckForm(data=valid_form_data(timeout=0))
        assert not form.is_valid()
        assert "timeout" in form.errors

    def test_timeout_above_max_rejected(self):
        form = CheckForm(data=valid_form_data(timeout=31))
        assert not form.is_valid()
        assert "timeout" in form.errors


@pytest.mark.django_db
class TestInterval:
    def test_valid_interval(self):
        form = CheckForm(data=valid_form_data(interval=30))
        assert form.is_valid(), form.errors

    def test_interval_below_min_rejected(self):
        form = CheckForm(data=valid_form_data(interval=0))
        assert not form.is_valid()
        assert "interval" in form.errors

    def test_interval_above_max_rejected(self):
        form = CheckForm(data=valid_form_data(interval=61))
        assert not form.is_valid()
        assert "interval" in form.errors


@pytest.mark.django_db
class TestAlertThreshold:
    def test_valid_threshold(self):
        form = CheckForm(data=valid_form_data(alert_threshold=3))
        assert form.is_valid(), form.errors

    def test_threshold_below_min_rejected(self):
        form = CheckForm(data=valid_form_data(alert_threshold=0))
        assert not form.is_valid()
        assert "alert_threshold" in form.errors


@pytest.mark.django_db
class TestMethodField:
    def test_default_method_for_new_form(self):
        form = CheckForm()
        assert form.initial.get("method") == "GET"

    def test_method_hidden_widget(self):
        form = CheckForm()
        assert form.fields["method"].widget.__class__.__name__ == "HiddenInput"

    def test_post_method_accepted(self):
        form = CheckForm(data=valid_form_data(method="POST"))
        assert form.is_valid(), form.errors
        assert form.cleaned_data["method"] == "POST"
