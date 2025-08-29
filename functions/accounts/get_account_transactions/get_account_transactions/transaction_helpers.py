from aws_lambda_powertools import Logger
from boto3.dynamodb.conditions import Key

from .date_helpers import get_date_range


def query_transactions(
    table,
    account_id: str,
    logger: Logger,
    period: str = None,
    start: str = None,
    end: str = None,
    descending=False,
):
    statement_period, start_iso, end_iso = get_date_range(period, start, end)

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
