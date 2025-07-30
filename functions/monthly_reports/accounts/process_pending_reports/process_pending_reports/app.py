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

from sqs import get_sqs_client
from sfn import get_sfn_client

ENVIRONMENT_NAME = os.environ.get("ENVIRONMENT_NAME", "dev")
POWERTOOLS_LOG_LEVEL = os.environ.get("POWERTOOLS_LOG_LEVEL", "INFO").upper()
ACCOUNTS_TABLE_NAME = os.environ.get("ACCOUNTS_TABLE_NAME")
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
SQS_ENDPOINT = os.environ.get("SQS_ENDPOINT")
CONTINUATION_QUEUE_URL = os.environ.get("CONTINUATION_QUEUE_URL")
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
    logger.info("Processing SQS continuation messages")

    metrics = initialize_metrics()

    try:
        # Process each SQS record
        for record in event.get("Records", []):
            message_body = json.loads(record["body"])
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
                )
                merge_metrics(metrics, batch_metrics)

            else:
                logger.warning(f"Unknown continuation type: {continuation_type}")

    except Exception as e:
        logger.error(
            f"Critical error during continuation processing: {e}", exc_info=True
        )
        raise

    return create_response(metrics, "COMPLETED", logger)
