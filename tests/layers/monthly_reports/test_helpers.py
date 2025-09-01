import datetime
from unittest.mock import patch

import pytest

from monthly_reports.helpers import get_statement_period


@pytest.mark.parametrize(
    "current_date, expected_period, description",
    [
        (
            datetime.datetime(2024, 1, 15, 14, 30, 45, 123456),
            "2023-12",
            "January mid-month",
        ),
        (datetime.datetime(2024, 1, 1, 0, 0, 0, 0), "2023-12", "January 1st midnight"),
        (
            datetime.datetime(2024, 1, 31, 23, 59, 59, 999999),
            "2023-12",
            "January 31st last second",
        ),
        (
            datetime.datetime(2024, 2, 28, 23, 59, 59, 999999),
            "2024-01",
            "February 28th non-leap year",
        ),
        (
            datetime.datetime(2024, 2, 29, 12, 0, 0, 0),
            "2024-01",
            "February 29th leap year",
        ),
        (
            datetime.datetime(2023, 2, 28, 12, 0, 0, 0),
            "2023-01",
            "February 28th leap year",
        ),
        (datetime.datetime(2024, 3, 1, 0, 0, 0, 0), "2024-02", "March 1st leap year"),
        (
            datetime.datetime(2023, 3, 1, 12, 0, 0, 0),
            "2023-02",
            "March 1st non-leap year",
        ),
        (datetime.datetime(2024, 6, 1, 0, 0, 0, 0), "2024-05", "June 1st"),
        (datetime.datetime(2024, 7, 31, 23, 59, 59, 999999), "2024-06", "July 31st"),
        (
            datetime.datetime(2024, 8, 15, 12, 30, 45, 123456),
            "2024-07",
            "August mid-month",
        ),
        (
            datetime.datetime(2024, 12, 31, 23, 59, 59, 999999),
            "2024-11",
            "December 31st",
        ),
        (datetime.datetime(2024, 5, 1, 0, 0, 0, 0), "2024-04", "First day midnight"),
        (
            datetime.datetime(2024, 5, 31, 23, 59, 59, 999999),
            "2024-04",
            "Last day last second",
        ),
    ],
)
@patch("monthly_reports.helpers.datetime")
def test_get_statement_period_parametrized(
    mock_datetime, current_date, expected_period, description
):
    mock_datetime.datetime.now.return_value = current_date
    mock_datetime.UTC = datetime.UTC
    mock_datetime.timedelta = datetime.timedelta

    result = get_statement_period()

    assert (
        result == expected_period
    ), f"Failed for {description}: expected {expected_period}, got {result}"
