from aws_lambda_powertools import Logger
from boto3.dynamodb.conditions import Key

from . import date_helpers


def query_transactions(
    table,
    account_id: str,
    logger: Logger,
    period: str = None,
    start: str = None,
    end: str = None,
    descending=False,
):
    """
    Query transactions for an account within a computed date range.

    Computes a statement period and ISO start/end datetimes via date_helpers.get_date_range(period, start, end),
    queries the table's "AccountDateIndex" for items where accountId equals `account_id` and createdAt is between
    the computed start and end, and returns the statement period and the matching transactions.

    Parameters:
        account_id (str): Account identifier to filter transactions.
        period (str, optional): Named period (e.g. billing period) used to derive the date range; passed to date_helpers.get_date_range.
        start (str, optional): ISO datetime string to override the start of the range; passed to date_helpers.get_date_range.
        end (str, optional): ISO datetime string to override the end of the range; passed to date_helpers.get_date_range.
        descending (bool, optional): If True, return transactions in descending order by createdAt.

    Returns:
        dict: {
            "statementPeriod": <str> statement period as returned by date_helpers.get_date_range,
            "transactions": <list> list of DynamoDB items (empty list if none)
        }

    Notes:
        - `table` and `logger` are service/client objects and are not documented here.
        - Any exceptions raised by date_helpers.get_date_range or the DynamoDB query propagate to the caller.
    """
    statement_period, start_iso, end_iso = date_helpers.get_date_range(
        period, start, end
    )

    logger.info(
        f"Querying transactions for account {account_id} "
        f"from {start_iso} to {end_iso} (period {statement_period})"
    )

    response = table.query(
        IndexName="AccountDateIndex",
        KeyConditionExpression=Key("accountId").eq(account_id)
        & Key("createdAt").between(start_iso, end_iso),
        ScanIndexForward=not descending,
    )

    return {
        "statementPeriod": statement_period,
        "transactions": response.get("Items", []),
    }
