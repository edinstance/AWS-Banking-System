import pytest
from functions.accounts.get_account_transactions.get_account_transactions.date_helpers import (
    get_date_range,
)
from functions.accounts.get_account_transactions.get_account_transactions.exceptions import (
    ValidationError,
)
from datetime import datetime, timezone


class TestGetDateRange:
    def test_period_and_start(self):
        with pytest.raises(
            ValidationError, match="Cannot combine 'period' with 'start'/'end'"
        ):
            get_date_range(period="june", start="june")

    def test_end_and_no_start(self):
        with pytest.raises(
            ValidationError, match="Both 'start' and 'end' must be provided together"
        ):
            get_date_range(end="june")

    def test_invalid_custom_date_format(self):
        with pytest.raises(
            ValidationError, match="Invalid date format, must be YYYY-MM-DD"
        ):
            get_date_range(start="2024/01/01", end="2024-01-10")

    def test_end_before_start(self):
        with pytest.raises(
            ValidationError, match="'end' date must be after 'start' date"
        ):
            get_date_range(start="2024-06-10", end="2024-06-09")

    def test_valid_custom_range_outputs(self):
        period, start_iso, end_iso = get_date_range(
            start="2024-06-10", end="2024-06-12"
        )
        assert period == "2024-06-10_to_2024-06-12"
        assert start_iso == "2024-06-10T00:00:00Z"
        assert end_iso == "2024-06-12T23:59:59Z"

    @pytest.mark.parametrize(
        "bad_period",
        ["june", "2024-13", "2024/06", "202406", "2024--06", "2024-0a"],
    )
    def test_invalid_period_format(self, bad_period):
        with pytest.raises(
            ValidationError, match="Invalid period format, must be YYYY-MM"
        ):
            get_date_range(period=bad_period)

    def test_valid_period_leap_february(self):
        period, start_iso, end_iso = get_date_range(period="2024-02")
        assert period == "2024-02"
        assert start_iso == "2024-02-01T00:00:00Z"
        assert end_iso == "2024-02-29T23:59:59Z"  # leap year

    def test_valid_period_april(self):
        period, start_iso, end_iso = get_date_range(period="2023-04")
        assert period == "2023-04"
        assert start_iso == "2023-04-01T00:00:00Z"
        assert end_iso == "2023-04-30T23:59:59Z"

    def test_base_case(self, monkeypatch):
        fake_now = datetime(2023, 3, 5, tzinfo=timezone.utc)

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return fake_now

        monkeypatch.setattr(
            "functions.accounts.get_account_transactions.get_account_transactions.date_helpers.datetime",
            FixedDateTime,
        )

        period, start_iso, end_iso = get_date_range()
        assert period == "2023-02"
        assert start_iso == "2023-02-01T00:00:00Z"
        assert end_iso == "2023-02-28T23:59:59Z"
