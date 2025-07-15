from decimal import Decimal
from typing import Dict, Any

from aws_lambda_powertools import Logger

from .exceptions import (
    TransactionProcessingError,
)

VALID_TRANSACTION_TYPES = {"DEPOSIT", "WITHDRAWAL"}


def validate_transaction_data(
    new_image: Dict[str, Any], logger: Logger
) -> Dict[str, Any]:
    """
    Validate and extract transaction details from a DynamoDB record dictionary.

    Checks for the presence and correctness of required transaction fields, converts values to appropriate types, and ensures the transaction type and amount are valid. Raises a TransactionProcessingError if validation fails.

    Parameters:
        new_image (Dict[str, Any]): A dictionary representing a DynamoDB record with attribute values.

    Returns:
        Dict[str, Any]: A dictionary containing validated and typed transaction details.
    """
    required_fields = ["accountId", "amount", "type", "userId", "id", "idempotencyKey"]

    missing_fields = [field for field in required_fields if field not in new_image]
    if missing_fields:
        raise TransactionProcessingError(f"Missing required fields: {missing_fields}")

    try:
        account_id = new_image["accountId"]["S"]
        amount = Decimal(new_image["amount"]["N"])
        transaction_type = new_image["type"]["S"].upper()
        user_id = new_image["userId"]["S"]
        transaction_id = new_image["id"]["S"]
        idempotency_key = new_image["idempotencyKey"]["S"]

        if transaction_type not in VALID_TRANSACTION_TYPES:
            raise TransactionProcessingError(
                f"Invalid transaction type: {transaction_type}"
            )

        if amount <= 0:
            raise TransactionProcessingError(f"Amount must be positive: {amount}")

        return {
            "account_id": account_id,
            "amount": amount,
            "transaction_type": transaction_type,
            "user_id": user_id,
            "transaction_id": transaction_id,
            "idempotency_key": idempotency_key,
        }

    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Error parsing DynamoDB record: {e}")
        logger.error(f"Available fields: {list(new_image.keys())}")
        raise TransactionProcessingError(f"Invalid record format: {e}")
