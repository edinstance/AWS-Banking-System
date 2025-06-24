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
    Check if a transaction with the specified idempotency key exists in the DynamoDB table.
    
    Returns:
        The transaction item dictionary if found; otherwise, None.
    
    Raises:
        Exception: If the DynamoDB table resource is not provided.
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
    Save a transaction record to DynamoDB using the provided transaction data.
    
    Raises an exception if the DynamoDB table resource is not configured or if a DynamoDB client error occurs. Relies on the uniqueness of the `idempotencyKey` hash key to enforce idempotency.
    
    Returns:
        True if the transaction is saved successfully.
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
    Constructs a transaction record dictionary for DynamoDB storage.
    
    Normalises and extracts transaction details from the request, sets creation and TTL timestamps, and includes metadata such as user, environment, and idempotency information.
    
    Parameters:
        transaction_id (str): Unique identifier for the transaction.
        request_body (dict): Transaction details from the incoming request.
        user_id (str): Identifier of the user initiating the transaction.
        idempotency_key (str): Key to ensure transaction idempotency.
        environment_name (str): Name of the deployment environment.
        request_id (str): Unique identifier for the request.
    
    Returns:
        dict: A dictionary representing the transaction item, suitable for insertion into DynamoDB.
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
