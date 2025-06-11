import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from decimal import DecimalException

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
    missing_fields = [field for field in required_fields if not data.get(field)]

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
    Attempts to save a transaction record to DynamoDB using a conditional write to ensure idempotency.

    The conditional write ensures that no transaction with the same idempotencyKey exists that hasn't expired.
    This provides atomic idempotency checking and writing in a single operation.

    Args:
        transaction_item (dict): The transaction data to be stored.
        table: The DynamoDB table to write to.
        logger: The logger to use.

    Returns:
        True if the transaction is saved successfully.

    Raises:
        ConditionalCheckFailedException: If a transaction with this idempotency key already exists.
        Exception: If the operation fails due to throughput limits, missing resources, or other database errors.
    """
    if not table:
        logger.error("DynamoDB table is not initialized for saving transaction.")
        raise Exception("Database not configured.")

    try:
        condition_expression = (
            "attribute_not_exists(idempotencyKey) OR " "idempotencyExpiration < :now"
        )
        expression_values = {":now": int(datetime.now(timezone.utc).timestamp())}

        table.put_item(
            Item=transaction_item,
            ConditionExpression=condition_expression,
            ExpressionAttributeValues=expression_values,
        )
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        logger.error(
            f"Failed to save transaction (Code: {error_code}): {e}", exc_info=True
        )
        if error_code == "ConditionalCheckFailedException":
            raise
        elif error_code == "ProvisionedThroughputExceededException":
            raise Exception("Service temporarily unavailable due to high load") from e
        elif error_code == "ResourceNotFoundException":
            raise Exception("Transaction database configuration error") from e
        else:
            raise Exception(f"Database error: {error_code}") from e


def build_transaction_item(
    transaction_id: str,
    request_body: dict,
    user_id: str,
    idempotency_key: str,
    idempotency_expiration_days: int,
    environment_name: str,
    request_id: str,
) -> dict:
    account_id = request_body["accountId"]
    transaction_type = request_body["type"].upper()
    description = request_body.get("description", "")
    amount = Decimal(str(request_body["amount"]))

    now_utc = datetime.now(timezone.utc)
    created_at_iso = now_utc.isoformat()

    ttl_datetime = now_utc + timedelta(days=365)
    ttl_timestamp = int(ttl_datetime.timestamp())

    idempotency_expiration = now_utc + timedelta(days=idempotency_expiration_days)
    idempotency_expiration_timestamp = int(idempotency_expiration.timestamp())

    sanitized_request_body = {
        "accountId": account_id,
        "userId": user_id,
        "amount": str(amount),
        "type": transaction_type,
        "description": description,
    }

    return {
        "id": transaction_id,
        "createdAt": created_at_iso,
        "accountId": account_id,
        "userId": user_id,
        "amount": amount,
        "type": transaction_type,
        "description": description,
        "status": "COMPLETED",
        "ttlTimestamp": ttl_timestamp,
        "idempotencyKey": idempotency_key,
        "idempotencyExpiration": idempotency_expiration_timestamp,
        "environment": environment_name,
        "requestId": request_id,
        "rawRequest": json.dumps(sanitized_request_body),
    }
