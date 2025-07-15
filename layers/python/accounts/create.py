import datetime
import uuid

from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError


def create_account_if_not_exists(
    table,
    logger: Logger,
    user_id: str,
) -> str:
    """
    Create a new account record in the DynamoDB table for the specified user if it does not already exist.
    
    Parameters:
        user_id (str): The unique identifier of the user for whom the account is to be created.
    
    Returns:
        str: The generated account ID for the newly created account.
    
    Raises:
        ValueError: If `user_id` is not provided.
        ClientError: If the DynamoDB operation fails.
    """
    if not user_id:
        raise ValueError("user_id is required")

    try:
        account_id = str(uuid.uuid4())

        account = {
            "accountId": account_id,
            "userId": user_id,
            "balance": 0,
            "createdAt": datetime.datetime.now(datetime.UTC).isoformat(),
            "updatedAt": datetime.datetime.now(datetime.UTC).isoformat(),
        }

        table.put_item(
            Item=account, ConditionExpression="attribute_not_exists(accountId)"
        )

        return account_id

    except ClientError as e:
        logger.error(f"DynamoDB ClientError: {str(e)}", exc_info=True)
        raise e
