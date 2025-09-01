from datetime import datetime, timedelta, timezone
import calendar

from .exceptions import ValidationError


def get_date_range(period: str = None, start: str = None, end: str = None):
    # --- Validation rules ---
    if period and (start or end):
        raise ValidationError("Cannot combine 'period' with 'start'/'end'")

    if (start and not end) or (end and not start):
        raise ValidationError("Both 'start' and 'end' must be provided together")

    # --- Custom range ---
    if start and end:
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end_dt = datetime.strptime(end, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        except ValueError:
            raise ValidationError("Invalid date format, must be YYYY-MM-DD")

        if end_dt < start_dt:
            raise ValidationError("'end' date must be after 'start' date")

        statement_period = (
            f"{start_dt.strftime('%Y-%m-%d')}_to_{end_dt.strftime('%Y-%m-%d')}"
        )

    # --- Period (month) ---
    elif period:
        try:
            year, month = map(int, period.split("-"))
            start_dt = datetime(year, month, 1, tzinfo=timezone.utc)
            last_day_num = calendar.monthrange(year, month)[1]
            end_dt = datetime(
                year, month, last_day_num, 23, 59, 59, tzinfo=timezone.utc
            )
        except Exception:
            raise ValidationError("Invalid period format, must be YYYY-MM")

        statement_period = start_dt.strftime("%Y-%m")

    # --- Default: last month ---
    else:
        today = datetime.now(timezone.utc)
        first_day_this_month = datetime(today.year, today.month, 1, tzinfo=timezone.utc)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        start_dt = datetime(
            last_day_last_month.year, last_day_last_month.month, 1, tzinfo=timezone.utc
        )
        end_dt = datetime(
            last_day_last_month.year,
            last_day_last_month.month,
            last_day_last_month.day,
            23,
            59,
            59,
            tzinfo=timezone.utc,
        )
        statement_period = start_dt.strftime("%Y-%m")

    start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return statement_period, start_iso, end_iso
