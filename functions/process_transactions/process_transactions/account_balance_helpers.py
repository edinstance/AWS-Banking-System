import datetime
from decimal import Decimal

from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from .exceptions import BusinessLogicError


def get_account_balance(account_id: str, logger: Logger, accounts_table) -> Decimal:
    try:
        response = accounts_table.get_item(
            Key={"accountId": account_id}, ProjectionExpression="balance"
        )
        if "Item" in response:
            return Decimal(str(response["Item"]["balance"]))
        raise BusinessLogicError(f"Account {account_id} not found in database")
    except BusinessLogicError as exception:
        raise exception
    except ClientError as e:
        logger.error(f"Failed to get account balance for {account_id}: {e}")
        raise SystemError(f"Failed to get account balance: {e}")
    except Exception as e:
        logger.error(f"Unexpected error getting account balance for {account_id}: {e}")
        raise SystemError(f"Unexpected error getting account balance: {e}")


def update_account_balance(
    account_id: str, new_balance: Decimal, logger: Logger, accounts_table
):
    try:
        accounts_table.update_item(
            Key={"accountId": account_id},
            UpdateExpression="SET balance = :balance, updatedAt = :updatedAt",
            ExpressionAttributeValues={
                ":balance": new_balance,
                ":updatedAt": datetime.datetime.now(datetime.UTC).isoformat(),
            },
        )
    except ClientError as e:
        logger.error(f"Failed to update account balance for {account_id}: {e}")
        raise SystemError(f"Failed to update account balance: {e}")
    except Exception as e:
        logger.error(f"Unexpected error updating account balance for {account_id}: {e}")
        raise SystemError(f"Unexpected error updating account balance: {e}")
