import datetime


def period_is_in_future(statement_period: str) -> bool:
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
