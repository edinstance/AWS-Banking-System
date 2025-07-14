import datetime
from typing import Dict, Any

from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from checks import check_account_exists_in_database, check_user_owns_account
from .account_balance_helpers import (
    get_account_balance,
    update_account_balance,
)
from .exceptions import (
    TransactionSystemError,
    BusinessLogicError,
)
from .validation import (
    validate_transaction_data,
)


def update_transaction_status(
    idempotency_key: str,
    status: str,
    logger: Logger,
    transactions_table,
    processed_at: str = None,
    failure_reason: str = None,
):
    try:
        if not transactions_table:
            logger.error("Transactions table not initialized")
            raise TransactionSystemError("Transactions table not configured")

        update_expression = "SET #status = :status"
        expression_attribute_names = {"#status": "status"}
        expression_attribute_values = {":status": status}

        if processed_at:
            update_expression += ", processedAt = :processedAt"
            expression_attribute_values[":processedAt"] = processed_at

        if failure_reason:
            update_expression += ", failureReason = :failureReason"
            expression_attribute_values[":failureReason"] = failure_reason

        transactions_table.update_item(
            Key={"idempotencyKey": idempotency_key},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
        )

        logger.debug(
            f"Updated transaction with idempotencyKey {idempotency_key} status to {status}"
        )

    except ClientError as e:
        logger.error(f"Failed to update transaction status for {idempotency_key}: {e}")
        raise TransactionSystemError(f"Failed to update transaction status: {e}")


def process_single_transaction(
    record: Dict[str, Any], logger: Logger, accounts_table, transactions_table
) -> None:
    try:
        new_image = record["dynamodb"]["NewImage"]

        try:
            transaction_data = validate_transaction_data(new_image, logger)
        except Exception as e:
            raise BusinessLogicError(f"Invalid transaction data: {e}")

        account_id = transaction_data["account_id"]
        user_id = transaction_data["user_id"]
        amount = transaction_data["amount"]
        transaction_type = transaction_data["transaction_type"]
        transaction_id = transaction_data["transaction_id"]
        idempotency_key = transaction_data["idempotency_key"]

        logger.info(
            f"Processing {transaction_type} transaction {transaction_id} for account {account_id}, amount: {amount}"
        )

        if not check_account_exists_in_database(account_id, accounts_table):
            logger.info(f"Account {account_id} does not exist in database")
            raise BusinessLogicError(f"Account {account_id} does not exist")

        if not check_user_owns_account(account_id, user_id, accounts_table):
            logger.info(f"User does not own account {user_id}")
            raise BusinessLogicError(
                f"User {user_id} does not own account {account_id}"
            )

        try:
            current_balance = get_account_balance(account_id, logger, accounts_table)
        except Exception as e:
            raise TransactionSystemError(f"Failed to retrieve account balance: {e}")

        if transaction_type == "DEPOSIT":
            new_balance = current_balance + amount
        elif transaction_type == "WITHDRAWAL":
            if current_balance < amount:
                raise BusinessLogicError(
                    f"Insufficient funds. Current balance: {current_balance}, Withdrawal amount: {amount}"
                )
            new_balance = current_balance - amount
        else:
            raise BusinessLogicError(
                f"Unsupported transaction type: {transaction_type}"
            )

        try:
            update_account_balance(account_id, new_balance, logger, accounts_table)
        except Exception as e:
            raise TransactionSystemError(f"Failed to update account balance: {e}")

        processed_at = datetime.datetime.now(datetime.UTC).isoformat()

        try:
            update_transaction_status(
                idempotency_key, "PROCESSED", logger, transactions_table, processed_at
            )
        except Exception as e:
            raise TransactionSystemError(
                f"Failed to update transaction status after processing: {e}"
            )

        logger.info(
            f"Successfully processed transaction {transaction_id}: "
            f"account {account_id} balance updated from {current_balance} to {new_balance}"
        )

    except (BusinessLogicError, TransactionSystemError):
        raise
    except Exception as e:
        error_msg = f"Unexpected error processing transaction: {str(e)}"
        logger.error(error_msg, extra={"record": record}, exc_info=True)
        raise TransactionSystemError(error_msg) from e
