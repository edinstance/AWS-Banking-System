import os

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from dynamodb import get_dynamodb_resource
from sqs import send_message_to_sqs
from .exceptions import BusinessLogicError, TransactionSystemError
from .sqs import format_sqs_message, get_message_attributes
from .transaction_helpers import process_single_transaction, update_transaction_status

ENVIRONMENT_NAME = os.environ.get("ENVIRONMENT_NAME", "dev")
POWERTOOLS_LOG_LEVEL = os.environ.get("POWERTOOLS_LOG_LEVEL", "INFO").upper()
ACCOUNTS_TABLE_NAME = os.environ.get("ACCOUNTS_TABLE_NAME")
TRANSACTIONS_TABLE_NAME = os.environ.get("TRANSACTIONS_TABLE_NAME")
TRANSACTION_PROCESSING_DLQ_URL = os.environ.get("TRANSACTION_PROCESSING_DLQ_URL")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
SQS_ENDPOINT = os.environ.get("SQS_ENDPOINT")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")

logger = Logger(service="ProcessTransactions", level=POWERTOOLS_LOG_LEVEL)

dynamodb = get_dynamodb_resource(DYNAMODB_ENDPOINT, AWS_REGION, logger)

if ACCOUNTS_TABLE_NAME:
    accounts_table = dynamodb.Table(ACCOUNTS_TABLE_NAME)
    logger.debug(f"Initialized DynamoDB table: {ACCOUNTS_TABLE_NAME}")
else:
    logger.critical("FATAL: ACCOUNTS_TABLE_NAME environment variable not set!")
    accounts_table = None

if TRANSACTIONS_TABLE_NAME:
    transactions_table = dynamodb.Table(TRANSACTIONS_TABLE_NAME)
    logger.debug(f"Initialized DynamoDB transactions table: {TRANSACTIONS_TABLE_NAME}")
else:
    logger.critical("FATAL: TRANSACTIONS_TABLE_NAME environment variable not set!")
    transactions_table = None

cognito_client = boto3.client("cognito-idp", region_name=AWS_REGION)


@logger.inject_lambda_context
def lambda_handler(event, _context: LambdaContext):
    """
    Handle DynamoDB stream INSERT events for transaction records, process each transaction, and route failures to a dead‑letter queue as needed.

    Processes only records with eventName "INSERT" from a DynamoDB stream event, invoking process_single_transaction for each. Business logic failures attempt to mark the transaction as FAILED (when an idempotency key is available) and fall back to sending a formatted message to the configured SQS DLQ; system or unknown errors are sent to the DLQ. Returns a summary of the batch processing counts.

    Parameters:
        event (dict): A DynamoDB Streams event payload containing a "Records" list; only records with "eventName" == "INSERT" are processed.

    Returns:
        dict: HTTP-style summary with keys:
            - statusCode (int): 200 on successful batch handling.
            - processedRecords (int): Number of INSERT records processed.
            - successful (int): Count of successfully processed transactions.
            - businessLogicFailures (int): Count of records that failed business validation.
            - systemFailures (int): Count of records that failed due to system/unknown errors.

    Raises:
        TransactionSystemError: If required DynamoDB tables are not initialised, or if one or more records could not be processed or delivered to the DLQ (critical failures).
    """
    logger.info("Processing DynamoDB stream event")

    if not accounts_table:
        raise TransactionSystemError("DynamoDB table not initialized")

    if not transactions_table:
        raise TransactionSystemError("Transactions table not initialized")

    records = event.get("Records", [])

    if not records:
        logger.info("No records to process")
        return {"statusCode": 200, "message": "No records to process"}

    transaction_inserts = [
        record for record in records if record.get("eventName") == "INSERT"
    ]

    if not transaction_inserts:
        logger.info("No INSERT records to process")
        return {"statusCode": 200, "message": "No INSERT records to process"}

    logger.info(f"Processing {len(transaction_inserts)} transaction records")

    successful_count = 0
    business_logic_failures = 0
    system_failures = 0
    critical_failures = 0

    for record in transaction_inserts:
        sequence_number = record.get("dynamodb", {}).get("SequenceNumber", "unknown")
        idempotency_key = None

        try:
            new_image = record.get("dynamodb", {}).get("NewImage", {})
            if "idempotencyKey" in new_image:
                idempotency_key = new_image["idempotencyKey"]["S"]

            process_single_transaction(
                record, logger, accounts_table, transactions_table
            )

            successful_count += 1
            logger.debug(f"Successfully processed record {sequence_number}")

        except BusinessLogicError as e:
            business_logic_failures += 1
            logger.warning(f"Business logic error for record {sequence_number}: {e}")

            if idempotency_key:
                try:
                    update_transaction_status(
                        idempotency_key,
                        "FAILED",
                        logger,
                        transactions_table,
                        failure_reason=str(e),
                    )
                    logger.info(
                        f"Marked transaction {idempotency_key} as FAILED with reason"
                    )
                except Exception as update_error:
                    logger.error(
                        f"Failed to update transaction status to FAILED: {update_error}"
                    )
                    if not send_message_to_sqs(
                        message=format_sqs_message(
                            record,
                            f"Failed to update status after business logic error: {e}",
                        ),
                        message_attributes=get_message_attributes(
                            error_type="StatusUpdateError",
                            environment_name=ENVIRONMENT_NAME,
                            idempotency_key=idempotency_key,
                        ),
                        sqs_endpoint=SQS_ENDPOINT,
                        sqs_url=TRANSACTION_PROCESSING_DLQ_URL,
                        aws_region=AWS_REGION,
                        logger=logger,
                    ):
                        critical_failures += 1
            else:
                logger.error(f"No idempotency key found for business logic error: {e}")
                if not send_message_to_sqs(
                    message=format_sqs_message(
                        record, f"Business logic error without idempotency key: {e}"
                    ),
                    message_attributes=get_message_attributes(
                        error_type="BusinessLogicError",
                        environment_name=ENVIRONMENT_NAME,
                        idempotency_key=idempotency_key,
                    ),
                    sqs_endpoint=SQS_ENDPOINT,
                    sqs_url=TRANSACTION_PROCESSING_DLQ_URL,
                    aws_region=AWS_REGION,
                    logger=logger,
                ):
                    critical_failures += 1

        except TransactionSystemError as e:
            system_failures += 1
            logger.error(f"System error for record {sequence_number}: {e}")

            if not send_message_to_sqs(
                message=format_sqs_message(record, str(e)),
                message_attributes=get_message_attributes(
                    error_type="TransactionSystemError",
                    environment_name=ENVIRONMENT_NAME,
                ),
                sqs_endpoint=SQS_ENDPOINT,
                sqs_url=TRANSACTION_PROCESSING_DLQ_URL,
                aws_region=AWS_REGION,
                logger=logger,
            ):
                critical_failures += 1
                logger.critical(
                    f"CRITICAL: Failed to send record {sequence_number} to DLQ"
                )

        except Exception as e:
            system_failures += 1
            logger.error(
                f"Unknown error for record {sequence_number}: {e}", exc_info=True
            )

            if not send_message_to_sqs(
                message=format_sqs_message(record, f"Unknown error: {str(e)}"),
                message_attributes=get_message_attributes(
                    error_type="UnknownError", environment_name=ENVIRONMENT_NAME
                ),
                sqs_endpoint=SQS_ENDPOINT,
                sqs_url=TRANSACTION_PROCESSING_DLQ_URL,
                aws_region=AWS_REGION,
                logger=logger,
            ):
                critical_failures += 1
                logger.critical(
                    f"CRITICAL: Failed to send record {sequence_number} to DLQ"
                )

    logger.info(
        f"Batch processing complete. "
        f"Success: {successful_count}, "
        f"Business Logic Failures: {business_logic_failures}, "
        f"System Failures: {system_failures}, "
        f"Critical Failures: {critical_failures}"
    )

    if critical_failures > 0:
        raise TransactionSystemError(
            f"Critical failure: {critical_failures} records could not be processed or sent to DLQ"
        )

    return {
        "statusCode": 200,
        "processedRecords": len(transaction_inserts),
        "successful": successful_count,
        "businessLogicFailures": business_logic_failures,
        "systemFailures": system_failures,
    }
