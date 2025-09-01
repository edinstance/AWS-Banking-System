import datetime


def get_statement_period():
    """
    Return the statement period for the previous month as "YYYY-MM".

    Uses the current UTC date/time to determine the first day of the current month at 00:00 UTC, subtracts one day to obtain the last day of the previous month, and returns that date formatted as "%Y-%m".
    """
    today = datetime.datetime.now(datetime.UTC)
    first_day_of_current_month = today.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    last_day_of_previous_month = first_day_of_current_month - datetime.timedelta(days=1)
    return last_day_of_previous_month.strftime("%Y-%m")
