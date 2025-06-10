from datetime import datetime, timezone
from decimal import Decimal, DecimalException

from aws_lambda_powertools import Logger
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from .helpers import is_valid_uuid


def validate_transaction_data(data, valid_transaction_types):
    """
    Validates transaction data against required fields and business rules.

    Checks for presence of required fields, valid transaction type, positive numeric amount, valid UUID for accountId, and ensures description is a string if provided.

    Args:
        data (dict): The transaction data to validate.
        valid_transaction_types (list): A list of valid transaction types.

    Returns:
        tuple: A tuple (is_valid, error_message), where is_valid is True if the data is valid, otherwise False, and error_message contains the reason for invalidity or None if valid.
    """
    required_fields = ["accountId", "amount", "type"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"

    normalised_types = {t.upper() for t in valid_transaction_types}
    if data["type"].upper() not in normalised_types:
        return (
            False,
            f"Invalid transaction type. Must be one of: {', '.join(valid_transaction_types)}",
        )

    try:
        amount = Decimal(str(data["amount"]))
    except (ValueError, TypeError, DecimalException):
        return False, "Invalid amount format. Amount must be a number."

    if amount <= 0:
        return False, "Amount must be a positive number"

    if not isinstance(data.get("accountId"), str) or not is_valid_uuid(
        data["accountId"]
    ):
        return False, "Invalid accountId, accountId must be a valid UUID"

    if "description" in data and not isinstance(data["description"], str):
        return False, "Description must be a string"

    return True, None


def check_existing_transaction(idempotency_key: str, table, logger: Logger):
    """
    Checks for an existing, non-expired transaction with the specified idempotency key.

    Queries the DynamoDB table using a secondary index to find a transaction matching the
    given idempotency key whose idempotency expiration timestamp is in the future.

    Args:
        idempotency_key: The idempotency key to search for.
        table: The DynamoDB table to query.
        logger: The logger to use.

    Returns:
        The existing transaction item as a dictionary if found and not expired; otherwise, None.

    Raises:
        ClientError: If a DynamoDB error occurs during the query.
    """
    if not table:
        logger.error("DynamoDB table is not initialized for idempotency check.")
        raise Exception("Database not configured.")

    try:
        response = table.query(
            IndexName="IdempotencyKeyIndex",
            KeyConditionExpression=Key("idempotencyKey").eq(idempotency_key),
            ConsistentRead=False,
        )

        items = response.get("Items", [])
        if items:
            now = int(datetime.now(timezone.utc).timestamp())
            for item in items:
                if item.get("idempotencyExpiration", 0) > now:
                    return item
                else:
                    logger.debug(
                        f"Expired or invalid idempotency item found for key {idempotency_key}"
                    )
        return None
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        logger.error(
            f"DynamoDB error checking idempotency (Code: {error_code}): {e}",
            exc_info=True,
        )
        if error_code == "ProvisionedThroughputExceededException":
            raise Exception("Service temporarily unavailable due to high load") from e
        raise


def save_transaction(transaction_item, table, logger: Logger):
    """
    Attempts to save a transaction record to DynamoDB, raising exceptions on failure.

    Args:
        transaction_item (dict): The transaction data to be stored.
        table: The DynamoDB table to query.
        logger: The logger to use.

    Returns:
        True if the transaction is saved successfully.

    Raises:
        Exception: If the operation fails due to throughput limits, missing resources, or other database errors.
    """
    if not table:
        logger.error("DynamoDB table is not initialized for saving transaction.")
        raise Exception("Database not configured.")

    try:
        table.put_item(Item=transaction_item)
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        logger.error(
            f"Failed to save transaction (Code: {error_code}): {e}", exc_info=True
        )
        if error_code == "ProvisionedThroughputExceededException":
            raise Exception("Service temporarily unavailable due to high load") from e
        elif error_code == "ResourceNotFoundException":
            raise Exception("Transaction database configuration error") from e
        else:
            raise Exception(f"Database error: {error_code}") from e
