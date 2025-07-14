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
