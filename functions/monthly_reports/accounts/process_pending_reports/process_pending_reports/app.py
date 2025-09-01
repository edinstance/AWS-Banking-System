import json
import os

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from dynamodb import get_dynamodb_resource
from monthly_reports.metrics import initialize_metrics, merge_metrics
from monthly_reports.processing import (
    process_accounts_scan_continuation,
    process_batch_continuation,
)
from monthly_reports.responses import create_response
from monthly_reports.sqs import send_bad_account_to_dlq

from sqs import get_sqs_client
from sfn import get_sfn_client

ENVIRONMENT_NAME = os.environ.get("ENVIRONMENT_NAME", "dev")
POWERTOOLS_LOG_LEVEL = os.environ.get("POWERTOOLS_LOG_LEVEL", "INFO").upper()
ACCOUNTS_TABLE_NAME = os.environ.get("ACCOUNTS_TABLE_NAME")
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
SQS_ENDPOINT = os.environ.get("SQS_ENDPOINT")
CONTINUATION_QUEUE_URL = os.environ.get("CONTINUATION_QUEUE_URL")
DLQ_URL = os.environ.get("DLQ_URL")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")

PAGE_SIZE = 50
BATCH_SIZE = 10
SAFETY_BUFFER = 30

logger = Logger(service="MonthlyAccountReportsContinuation", level=POWERTOOLS_LOG_LEVEL)

dynamodb = get_dynamodb_resource(DYNAMODB_ENDPOINT, AWS_REGION, logger)
sqs_client = get_sqs_client(SQS_ENDPOINT, AWS_REGION, logger)
sfn_client = get_sfn_client(AWS_REGION, logger)

if ACCOUNTS_TABLE_NAME:
    accounts_table = dynamodb.Table(ACCOUNTS_TABLE_NAME)
    logger.debug(f"Initialized DynamoDB table: {ACCOUNTS_TABLE_NAME}")
else:
    logger.critical("FATAL: ACCOUNTS_TABLE_NAME environment variable not set!")
    accounts_table = None


@logger.inject_lambda_context
def lambda_handler(event, context: LambdaContext):
    """
    Handle SQS continuation messages for monthly account report processing.

    Processes each record in the incoming SQS event, routes messages by their
    `continuation_type` (`"accounts_scan"` or `"batch_continuation"`) to the
    appropriate continuation handler, aggregates returned metrics and returns a
    completion response. Malformed messages or unknown continuation types are
    optionally sent to a configured dead-letter queue (DLQ). Critical errors are
    re-raised after attempting to publish error details to the DLQ.

    Parameters:
        event (dict): Lambda event containing SQS records. Each record is expected
            to have a JSON body and optional `messageAttributes.continuation_type`.
        context (LambdaContext): AWS Lambda context object.

    Returns:
        dict: Response produced by `create_response(metrics, "COMPLETED", logger)`.

    Raises:
        Exception: Any unexpected exception raised during processing is propagated
        after an attempt is made to publish error details to the DLQ.
    """
    logger.info("Processing SQS continuation messages")

    metrics = initialize_metrics()

    try:
        # Process each SQS record
        for record in event.get("Records", []):
            try:
                message_body = json.loads(record["body"])
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse message body as JSON: {e}")
                if DLQ_URL and AWS_REGION:
                    try:
                        error_data = {
                            "lambda_function": "process-pending-reports",
                            "error_type": "json_parse_error",
                            "raw_message": record.get("body"),
                            "message_id": record.get("messageId"),
                        }
                        send_bad_account_to_dlq(
                            error_data,
                            "unknown",
                            f"JSON parse error: {str(e)}",
                            SQS_ENDPOINT,
                            DLQ_URL,
                            AWS_REGION,
                            logger,
                        )
                    except Exception as dlq_error:
                        logger.error(f"Failed to send parse error to DLQ: {dlq_error}")
                continue

            message_attributes = record.get("messageAttributes", {})

            continuation_type = message_attributes.get("continuation_type", {}).get(
                "stringValue"
            )

            if continuation_type == "accounts_scan":
                logger.info("Processing accounts scan continuation")
                scan_metrics = process_accounts_scan_continuation(
                    message_body["scan_params"],
                    message_body["statement_period"],
                    context,
                    logger,
                    accounts_table,
                    sfn_client,
                    STATE_MACHINE_ARN,
                    SQS_ENDPOINT,
                    CONTINUATION_QUEUE_URL,
                    AWS_REGION,
                    PAGE_SIZE,
                    BATCH_SIZE,
                    SAFETY_BUFFER,
                    DLQ_URL,
                )
                merge_metrics(metrics, scan_metrics)

            elif continuation_type == "batch_continuation":
                logger.info("Processing batch continuation")
                batch_metrics = process_batch_continuation(
                    message_body["scan_params"],
                    message_body["statement_period"],
                    message_body["remaining_accounts"],
                    message_body.get("last_evaluated_key"),
                    context,
                    logger,
                    accounts_table,
                    sfn_client,
                    STATE_MACHINE_ARN,
                    SQS_ENDPOINT,
                    CONTINUATION_QUEUE_URL,
                    AWS_REGION,
                    PAGE_SIZE,
                    BATCH_SIZE,
                    SAFETY_BUFFER,
                    DLQ_URL,
                )
                merge_metrics(metrics, batch_metrics)

            else:
                logger.warning(f"Unknown continuation type: {continuation_type}")
                if DLQ_URL and AWS_REGION:
                    try:
                        error_data = {
                            "lambda_function": "process-pending-reports",
                            "error_type": "unknown_continuation_type",
                            "continuation_type": continuation_type,
                            "message_body": message_body,
                            "message_id": record.get("messageId"),
                        }
                        statement_period = message_body.get(
                            "statement_period", "unknown"
                        )
                        send_bad_account_to_dlq(
                            error_data,
                            statement_period,
                            f"Unknown continuation type: {continuation_type}",
                            SQS_ENDPOINT,
                            DLQ_URL,
                            AWS_REGION,
                            logger,
                        )
                    except Exception as dlq_error:
                        logger.error(
                            f"Failed to send unknown continuation type to DLQ: {dlq_error}"
                        )

    except Exception as e:
        logger.error(
            f"Critical error during continuation processing: {e}", exc_info=True
        )
        if DLQ_URL and AWS_REGION:
            try:

                error_account = {
                    "lambda_function": "process-pending-reports",
                    "error_type": "critical_lambda_error",
                    "error_details": str(e),
                    "event": event,
                }
                send_bad_account_to_dlq(
                    error_account,
                    "unknown",
                    f"Critical lambda error: {str(e)}",
                    SQS_ENDPOINT,
                    DLQ_URL,
                    AWS_REGION,
                    logger,
                )
            except Exception as dlq_error:
                logger.error(f"Failed to send critical error to DLQ: {dlq_error}")
        raise

    return create_response(metrics, "COMPLETED", logger)
