import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from decimal import DecimalException

from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from .helpers import is_valid_uuid


def validate_transaction_data(data, valid_transaction_types):
    """
    Validates transaction data for required fields and business rules.

    Checks that the transaction includes a valid account ID (UUID), a positive numeric amount, a supported transaction type (case-insensitive), and that the optional description is a string if present.

    Args:
        data: The transaction data to validate.
        valid_transaction_types: List of allowed transaction types.

    Returns:
        Tuple of (is_valid, error_message), where is_valid is True if the data is valid, otherwise False, and error_message provides the reason for invalidity or None if valid.
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
    Checks for an existing transaction with the given idempotency key.

    Since idempotencyKey is the partition key, we can directly get the item.
    DynamoDB TTL will automatically remove expired items, so if we find an item,
    it's still valid.

    Args:
        idempotency_key: The idempotency key to check.
        table: The DynamoDB table resource.
        logger: Logger instance for recording operations.

    Returns:
        The transaction item if found, None otherwise.

    Raises:
        Exception: If the DynamoDB table is not configured.
        ClientError: If a DynamoDB client error occurs.
    """
    if not table:
        logger.error("DynamoDB table is not initialized for idempotency check.")
        raise Exception("Database not configured.")

    try:
        # Since idempotencyKey is the hash key, we can use get_item directly
        response = table.get_item(Key={"idempotencyKey": idempotency_key})

        item = response.get("Item")
        if item:
            logger.debug(
                f"Found existing transaction for idempotency key: {idempotency_key}"
            )
            return item

        return None
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        logger.error(
            f"DynamoDB error checking idempotency (Code: {error_code}): {e}",
            exc_info=True,
        )
        raise


def save_transaction(transaction_item, table, logger: Logger):
    """
    Saves a transaction record to DynamoDB.

    Since idempotencyKey is the hash key, attempting to save a transaction with an existing
    idempotencyKey will automatically fail with a ConditionalCheckFailedException.
    This provides built-in idempotency without needing additional conditional expressions.

    Args:
        transaction_item: The transaction data to save.
        table: The DynamoDB table resource.
        logger: Logger instance for recording operations.

    Returns:
        True if the transaction is saved successfully.

    Raises:
        Exception: If the DynamoDB table is not configured.
        ConditionalCheckFailedException: If a transaction with this idempotency key already exists.
        ClientError: For other DynamoDB errors.
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
        raise  # Let the caller handle all errors


def build_transaction_item(
    transaction_id: str,
    request_body: dict,
    user_id: str,
    idempotency_key: str,
    environment_name: str,
    request_id: str,
) -> dict:
    """
    Builds a transaction item dictionary for storage in DynamoDB.

    Assembles all required transaction fields, including normalised and serialised request data,
    timestamps for creation and TTL, as well as metadata such as user and environment identifiers.

    Args:
        transaction_id: Unique identifier for the transaction.
        request_body: Dictionary containing transaction details from the request.
        user_id: Identifier of the user performing the transaction.
        idempotency_key: Key used to ensure idempotency of the transaction.
        environment_name: Name of the environment (e.g., "prod", "dev").
        request_id: Unique identifier for the request.

    Returns:
        A dictionary representing the transaction item, ready for insertion into DynamoDB.
    """
    account_id = request_body["accountId"]
    transaction_type = request_body["type"].upper()
    description = request_body.get("description", "")
    amount = Decimal(str(request_body["amount"]))

    now_utc = datetime.now(timezone.utc)
    created_at_iso = now_utc.isoformat()

    ttl_datetime = now_utc + timedelta(days=365)
    ttl_timestamp = int(ttl_datetime.timestamp())

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
        "status": "PENDING",
        "ttlTimestamp": ttl_timestamp,
        "idempotencyKey": idempotency_key,
        "environment": environment_name,
        "requestId": request_id,
        "rawRequest": json.dumps(sanitized_request_body),
    }
