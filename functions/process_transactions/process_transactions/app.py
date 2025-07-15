import os

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from dynamodb import get_dynamodb_resource
from sqs import send_dynamodb_record_to_dlq
from .exceptions import BusinessLogicError, TransactionSystemError
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
    Processes DynamoDB stream INSERT events for transaction records, handling business and system errors with DLQ fallback.
    
    This AWS Lambda handler filters incoming DynamoDB stream events for new transaction inserts, processes each transaction, and manages error handling by updating transaction status or sending failed records to a dead-letter queue (DLQ) as appropriate. It returns a summary of processing results, including counts of successful and failed records.
    
    Parameters:
        event (dict): The DynamoDB stream event payload.
    
    Returns:
        dict: A summary containing the status code, number of processed records, and counts of successful, business logic, and system failures.
    
    Raises:
        TransactionSystemError: If critical failures occur that prevent records from being processed or sent to the DLQ.
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
                    if not send_dynamodb_record_to_dlq(
                        record=record,
                        sqs_url=SQS_ENDPOINT,
                        dlq_url=TRANSACTION_PROCESSING_DLQ_URL,
                        aws_region=AWS_REGION,
                        error_message=f"Failed to update status after business logic error: {e}",
                        logger=logger,
                    ):
                        critical_failures += 1
            else:
                logger.error(f"No idempotency key found for business logic error: {e}")
                if not send_dynamodb_record_to_dlq(
                    record=record,
                    sqs_url=SQS_ENDPOINT,
                    dlq_url=TRANSACTION_PROCESSING_DLQ_URL,
                    aws_region=AWS_REGION,
                    error_message=f"Business logic error without idempotency key: {e}",
                    logger=logger,
                ):
                    critical_failures += 1

        except TransactionSystemError as e:
            system_failures += 1
            logger.error(f"System error for record {sequence_number}: {e}")

            if not send_dynamodb_record_to_dlq(
                record=record,
                sqs_url=SQS_ENDPOINT,
                dlq_url=TRANSACTION_PROCESSING_DLQ_URL,
                aws_region=AWS_REGION,
                error_message=str(e),
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

            if not send_dynamodb_record_to_dlq(
                record=record,
                sqs_url=SQS_ENDPOINT,
                dlq_url=TRANSACTION_PROCESSING_DLQ_URL,
                aws_region=AWS_REGION,
                error_message=f"Unknown error: {str(e)}",
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
