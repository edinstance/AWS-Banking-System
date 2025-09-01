import os

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from dynamodb import get_dynamodb_resource, get_paginated_table_data
from monthly_reports.helpers import get_statement_period
from monthly_reports.metrics import initialize_metrics, merge_metrics
from monthly_reports.processing import process_accounts_page
from monthly_reports.responses import create_response
from monthly_reports.sqs import send_continuation_message
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

logger = Logger(service="MonthlyAccountReportsTrigger", level=POWERTOOLS_LOG_LEVEL)

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
def lambda_handler(_event, context: LambdaContext):
    logger.info("Starting monthly account reports processing from EventBridge trigger")

    statement_period = get_statement_period()
    logger.info(f"Starting new processing for period: {statement_period}")

    metrics = initialize_metrics()

    if not CONTINUATION_QUEUE_URL:
        logger.critical("CONTINUATION_QUEUE_URL is not set. Cannot test SQS sending.")
        return create_response(metrics, "ERROR_NO_CONTINUATION_QUEUE", logger)

    scan_params = {
        "ProjectionExpression": "accountId, userId, balance",
    }

    try:
        while True:
            remaining_time = context.get_remaining_time_in_millis() / 1000.0
            if remaining_time < SAFETY_BUFFER:
                logger.warning(
                    f"Approaching Lambda timeout. Processed {metrics['pages_processed']} pages."
                )
                send_continuation_message(
                    scan_params,
                    statement_period,
                    None,
                    None,
                    "accounts_scan",
                    SQS_ENDPOINT,
                    CONTINUATION_QUEUE_URL,
                    AWS_REGION,
                    logger,
                )
                return create_response(metrics, "TIMEOUT_CONTINUATION", logger)

            accounts_page, last_evaluated_key = get_paginated_table_data(
                scan_params=scan_params,
                index_name=None,
                table=accounts_table,
                logger=logger,
                page_size=PAGE_SIZE,
            )

            metrics["pages_processed"] += 1

            if not accounts_page:
                logger.info("No more accounts to process")
                break

            page_metrics = process_accounts_page(
                accounts_page,
                statement_period,
                context,
                logger,
                sfn_client,
                STATE_MACHINE_ARN,
                scan_params,
                last_evaluated_key,
                SQS_ENDPOINT,
                CONTINUATION_QUEUE_URL,
                AWS_REGION,
                BATCH_SIZE,
                SAFETY_BUFFER,
                DLQ_URL,
            )

            merge_metrics(metrics, page_metrics)

            if last_evaluated_key:
                scan_params["ExclusiveStartKey"] = last_evaluated_key
                logger.debug("More pages available, continuing...")
            else:
                logger.info("All pages processed successfully")
                break

    except Exception as e:
        logger.error(f"Critical error during processing: {e}", exc_info=True)
        if DLQ_URL and AWS_REGION:
            try:
                error_account = {
                    "lambda_function": "monthly-reports-trigger",
                    "error_type": "critical_lambda_error",
                    "error_details": str(e),
                }
                send_bad_account_to_dlq(
                    error_account,
                    statement_period,
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
