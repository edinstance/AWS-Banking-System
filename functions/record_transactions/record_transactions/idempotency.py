from aws_lambda_powertools import Logger

from .helpers import create_response
from .transactions import check_existing_transaction


def handle_idempotency_check(idempotency_key, table, logger: Logger):
    """
    Checks for an existing transaction using the idempotency key and returns an appropriate HTTP response.
    
    If a transaction with the given idempotency key exists, returns a 201 response indicating the transaction was already recorded and is idempotent. If no transaction is found, returns None. If an error occurs during the check, returns a 500 response indicating a failure to verify transaction uniqueness.
    """
    try:
        existing_transaction = check_existing_transaction(
            idempotency_key, table, logger
        )
        if existing_transaction:
            logger.info(
                f"Found existing transaction with ID: {existing_transaction.get('id')} for idempotency key {idempotency_key}"
            )
            return create_response(
                201,
                {
                    "message": "Transaction recorded successfully!",
                    "transactionId": existing_transaction["id"],
                    "idempotent": True,
                },
                "OPTIONS,POST",
            )
        return None
    except Exception as e:
        logger.error(f"Error checking idempotency: {str(e)}")
        return create_response(
            500,
            {"error": "Unable to verify transaction uniqueness. Please try again."},
            "OPTIONS,POST",
        )


def handle_idempotency_error(idempotency_key, table, logger, transaction_id, error):
    """
    Handles errors encountered during transaction recording with idempotency checks.
    
    If the error indicates a duplicate transaction ("ConditionalCheckFailedException"), attempts to retrieve the existing transaction and returns a 409 HTTP response with relevant details. For other errors, logs the failure and returns a 500 HTTP response indicating the transaction could not be processed.
    """
    error_code = error.response.get("Error", {}).get("Code")

    if error_code == "ConditionalCheckFailedException":
        try:
            existing_transaction = check_existing_transaction(
                idempotency_key, table, logger
            )
            if existing_transaction:
                return create_response(
                    409,
                    {
                        "error": "Transaction already processed",
                        "transactionId": existing_transaction["id"],
                        "idempotent": True,
                    },
                    "OPTIONS,POST",
                )
        except Exception:
            return create_response(
                409,
                {
                    "error": "Transaction already processed",
                    "idempotent": True,
                },
                "OPTIONS,POST",
            )

    logger.error(
        f"Failed to save transaction {transaction_id}: {str(error)}", exc_info=True
    )

    return create_response(
        500,
        {"error": "Failed to process transaction. Please try again."},
        "OPTIONS,POST",
    )
