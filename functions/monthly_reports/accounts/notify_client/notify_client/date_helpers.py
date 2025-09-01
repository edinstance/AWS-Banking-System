import datetime


def period_is_in_future(statement_period: str) -> bool:
    """
    Return True if the given statement period (YYYY-MM) falls in the current UTC month or a future month.

    Parameters:
        statement_period (str): Month in "YYYY-MM" format to check.

    Returns:
        bool: True when the period is the current month or later (using UTC); False if it is a past month.

    Raises:
        ValueError: If `statement_period` is not in the "YYYY-MM" format.
    """
    try:
        requested_date = datetime.datetime.strptime(statement_period, "%Y-%m")
    except ValueError:
        raise ValueError("Invalid statement_period format. Use 'YYYY-MM'.")

    requested_month = datetime.datetime(
        requested_date.year, requested_date.month, 1, tzinfo=datetime.timezone.utc
    )

    today = datetime.datetime.now(datetime.timezone.utc)
    current_month = datetime.datetime(
        today.year, today.month, 1, tzinfo=datetime.timezone.utc
    )

    return requested_month >= current_month
