import datetime

import pytest
from dateutil.relativedelta import relativedelta

from functions.monthly_reports.accounts.notify_client.notify_client.date_helpers import (
    period_is_in_future,
)


class TestPeriodIsInFuture:
    def test_period_is_current_month(self):
        today = datetime.datetime.now(datetime.UTC).strftime("%Y-%m")
        result = period_is_in_future(today)
        assert result is True

    def test_period_is_future_month(self):
        today = datetime.datetime.now(datetime.timezone.utc)
        one_year_later = today + relativedelta(years=1)
        result = period_is_in_future(one_year_later.strftime("%Y-%m"))
        assert result is True

    def test_period_is_in_the_past(self):
        today = datetime.datetime.now(datetime.timezone.utc)
        one_year_before = today - relativedelta(years=1)
        result = period_is_in_future(one_year_before.strftime("%Y-%m"))
        assert result is False

    def test_invalid_format(self):
        with pytest.raises(
            ValueError, match="Invalid statement_period format. Use 'YYYY-MM'."
        ):
            today = datetime.datetime.now(datetime.UTC)
            period_is_in_future(today.strftime("%Y/%m"))

    def test_invalid_month(self):
        with pytest.raises(
            ValueError, match="Invalid statement_period format. Use 'YYYY-MM'."
        ):
            period_is_in_future("2025-13")

    def test_empty_string(self):
        with pytest.raises(
            ValueError, match="Invalid statement_period format. Use 'YYYY-MM'."
        ):
            period_is_in_future("")
