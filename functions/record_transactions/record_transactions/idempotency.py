from .helpers import create_response
from .transactions import check_existing_transaction


def handle_idempotency_error(idempotency_key, table, logger, transaction_id, error):
    """
    Process errors encountered during transaction recording with idempotency enforcement.

    If a duplicate transaction is detected, attempts to retrieve and report the existing transaction with a 409 response. For other errors, logs the failure and returns a 500 response indicating the transaction could not be processed.
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
                        "message": "Transaction already processed",
                        "transactionId": existing_transaction["id"],
                        "idempotent": True,
                    },
                    "OPTIONS,POST",
                )
        except Exception:
            return create_response(
                500,
                {
                    "message": "Error retrieving existing transaction",
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
