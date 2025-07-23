from aws_lambda_powertools.event_handler.exceptions import InternalServerError

from .transactions import check_existing_transaction


def handle_idempotency_error(idempotency_key, table, logger, transaction_id, error):
    """
    Handles errors during transaction recording with idempotency enforcement.

    If a duplicate transaction is detected, attempts to retrieve and return information about the existing transaction with a 409 status code. For other errors, logs the failure and raises an InternalServerError to indicate the transaction could not be processed.
    """
    error_code = error.response.get("Error", {}).get("Code")

    if error_code == "ConditionalCheckFailedException":
        try:
            existing_transaction = check_existing_transaction(
                idempotency_key, table, logger
            )
            if existing_transaction:
                return {
                    "message": "Transaction already processed.",
                    "transactionId": existing_transaction["id"],
                }, 409

        except Exception:
            raise InternalServerError("Error retrieving existing transaction.")

    logger.error(
        f"Failed to save transaction {transaction_id}: {str(error)}", exc_info=True
    )

    raise InternalServerError("Failed to process transaction. Please try again.")
