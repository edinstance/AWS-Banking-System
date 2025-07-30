import datetime


def get_statement_period():
    """Get the statement period for the previous month"""
    today = datetime.datetime.now(datetime.UTC)
    first_day_of_current_month = today.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    last_day_of_previous_month = first_day_of_current_month - datetime.timedelta(days=1)
    return last_day_of_previous_month.strftime("%Y-%m")
