import datetime
import uuid

from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError


def create_account_if_not_exists(
    table,
    logger: Logger,
    user_id: str,
) -> str:
    if not user_id:
        raise ValueError("user_id is required")

    try:
        account_id = str(uuid.uuid4())

        account = {
            "accountId": account_id,
            "userId": user_id,
            "balance": 0,
            "createdAt": datetime.datetime.now(datetime.UTC).isoformat(),
        }

        table.put_item(
            Item=account, ConditionExpression="attribute_not_exists(accountId)"
        )

        return account_id

    except ClientError as e:
        logger.error(f"DynamoDB ClientError: {str(e)}", exc_info=True)
        raise e
