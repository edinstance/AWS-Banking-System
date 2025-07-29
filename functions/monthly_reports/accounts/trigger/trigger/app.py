import datetime
import os

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from dynamodb import get_dynamodb_resource, get_paginated_table_data
from sqs import get_sqs_client, send_message_to_sqs
from sfn import get_sfn_client
from .processing import chunk_accounts, process_account_batch
from .responses import create_response

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

    today = datetime.datetime.now(datetime.UTC)
    first_day_of_current_month = today.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    last_day_of_previous_month = first_day_of_current_month - datetime.timedelta(days=1)
    statement_period = last_day_of_previous_month.strftime("%Y-%m")

    logger.info(f"Starting new processing for period: {statement_period}")

    metrics = {
        "processed_count": 0,
        "failed_starts_count": 0,
        "skipped_count": 0,
        "already_exists_count": 0,
        "batches_processed": 0,
        "pages_processed": 0,
    }

    if not CONTINUATION_QUEUE_URL:
        logger.critical("CONTINUATION_QUEUE_URL is not set. Cannot test SQS sending.")
        return create_response(metrics, "ERROR_NO_CONTINUATION_QUEUE", logger)

    scan_params = {
        "ProjectionExpression": "accountId, userId",
    }

    try:
        while True:
            remaining_time = context.get_remaining_time_in_millis() / 1000.0
            if remaining_time < SAFETY_BUFFER:
                logger.warning(
                    f"Approaching Lambda timeout. Processed {metrics['pages_processed']} pages."
                )
                message_body = {
                    "scan_params": scan_params,
                    "statement_period": statement_period,
                }
                message_attributes = {
                    "continuation_type": {
                        "DataType": "String",
                        "StringValue": "accounts_scan",
                    }
                }
                send_message_to_sqs(
                    message=message_body,
                    message_attributes=message_attributes,
                    sqs_endpoint=SQS_ENDPOINT,
                    sqs_url=CONTINUATION_QUEUE_URL,
                    aws_region=AWS_REGION,
                    logger=logger,
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

            account_batches = list(chunk_accounts(accounts_page, chunk_size=BATCH_SIZE))
            logger.info(
                f"Processing {len(accounts_page)} accounts in {len(account_batches)} batches"
            )

            for i, batch in enumerate(account_batches):
                remaining_time = context.get_remaining_time_in_millis() / 1000.0

                if remaining_time < SAFETY_BUFFER:
                    logger.warning(
                        f"Timeout approaching during batch processing. "
                        f"Processed {i}/{len(account_batches)} batches from current page."
                    )

                    if CONTINUATION_QUEUE_URL:
                        remaining_batches = account_batches[i:]
                        remaining_accounts = []
                        for remaining_batch in remaining_batches:
                            remaining_accounts.extend(remaining_batch)

                        message_body = {
                            "scan_params": scan_params,
                            "statement_period": statement_period,
                            "remaining_accounts": remaining_accounts,
                            "last_evaluated_key": last_evaluated_key,
                        }
                        message_attributes = {
                            "continuation_type": {
                                "DataType": "String",
                                "StringValue": "batch_continuation",
                            }
                        }
                        send_message_to_sqs(
                            message=message_body,
                            message_attributes=message_attributes,
                            sqs_endpoint=SQS_ENDPOINT,
                            sqs_url=CONTINUATION_QUEUE_URL,
                            aws_region=AWS_REGION,
                            logger=logger,
                        )
                    return create_response(metrics, "TIMEOUT_CONTINUATION", logger)

                try:
                    logger.info(
                        f"Processing batch {i + 1}/{len(account_batches)} "
                        f"with {len(batch)} accounts"
                    )

                    batch_result = process_account_batch(
                        batch, statement_period, sfn_client, logger, STATE_MACHINE_ARN
                    )

                    for key, value in batch_result.items():
                        metrics_key = f"{key}_count"
                        if metrics_key in metrics:
                            metrics[metrics_key] += value

                    metrics["batches_processed"] += 1

                except Exception as e:
                    logger.error(f"Error processing batch {i + 1}: {e}")
                    metrics["failed_starts_count"] += len(batch)

            if last_evaluated_key:
                scan_params["ExclusiveStartKey"] = last_evaluated_key
                logger.debug("More pages available, continuing...")
            else:
                logger.info("All pages processed successfully")
                break

    except Exception as e:
        logger.error(f"Critical error during processing: {e}", exc_info=True)
        raise

    return create_response(metrics, "COMPLETED", logger)
