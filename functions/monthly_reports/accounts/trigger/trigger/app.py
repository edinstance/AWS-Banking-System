import datetime
import json
import os
import time

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from dynamodb import get_dynamodb_resource, get_all_table_data
from sfn import get_sfn_client
from .processing import chunk_accounts, process_account_batch

ENVIRONMENT_NAME = os.environ.get("ENVIRONMENT_NAME", "dev")
POWERTOOLS_LOG_LEVEL = os.environ.get("POWERTOOLS_LOG_LEVEL", "INFO").upper()
ACCOUNTS_TABLE_NAME = os.environ.get("ACCOUNTS_TABLE_NAME")
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")

logger = Logger(service="MonthlyAccountReportsTrigger", level=POWERTOOLS_LOG_LEVEL)

dynamodb = get_dynamodb_resource(DYNAMODB_ENDPOINT, AWS_REGION, logger)
if ACCOUNTS_TABLE_NAME:
    accounts_table = dynamodb.Table(ACCOUNTS_TABLE_NAME)
    logger.debug(f"Initialized DynamoDB table: {ACCOUNTS_TABLE_NAME}")
else:
    logger.critical("FATAL: ACCOUNTS_TABLE_NAME environment variable not set!")
    table = None


sfn_client = get_sfn_client(AWS_REGION, logger)


@logger.inject_lambda_context
def lambda_handler(_event, context: LambdaContext):
    logger.info("Starting monthly account monthly_reports.")

    today = datetime.datetime.now(datetime.UTC)
    first_day_of_current_month = today.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    last_day_of_previous_month = first_day_of_current_month - datetime.timedelta(days=1)
    statement_period = last_day_of_previous_month.strftime("%Y-%m")

    logger.info(f"Generating statements for period: {statement_period}")

    metrics = {
        "processed_count": 0,
        "failed_starts_count": 0,
        "skipped_count": 0,
        "already_exists_count": 0,
        "batches_processed": 0,
    }

    start_time = time.time()
    lambda_timeout = context.get_remaining_time_in_millis() / 1000.0
    safety_buffer = 30

    scan_params = {
        "ProjectionExpression": "accountId, userId",
    }

    try:

        accounts_to_process = get_all_table_data(
            scan_params=scan_params,
            index_name=None,
            table=accounts_table,
            logger=logger,
        )

        logger.info(f"Retrieved {len(accounts_to_process)} accounts for processing.")

        account_batches = list(chunk_accounts(accounts_to_process, chunk_size=10))
        logger.info(
            f"Split into {len(account_batches)} batches of up to 10 accounts each."
        )

        for i, batch in enumerate(account_batches):
            elapsed_time = time.time() - start_time
            remaining_time = lambda_timeout - elapsed_time

            if remaining_time < safety_buffer:
                logger.warning(
                    f"Approaching Lambda timeout. Processed {i}/{len(account_batches)} batches."
                )
                break

            try:
                logger.info(
                    f"Processing batch {i + 1}/{len(account_batches)} with {len(batch)} accounts"
                )

                batch_result = process_account_batch(
                    batch, statement_period, sfn_client, logger, STATE_MACHINE_ARN
                )

                for key, value in batch_result.items():
                    metrics_key = f"{key}_count"
                    if metrics_key in metrics:
                        metrics[metrics_key] += value

                metrics["batches_processed"] += 1

                logger.debug(f"Batch {i + 1} result: {batch_result}")

            except Exception as e:
                logger.error(f"Unexpected error processing batch {i + 1}: {e}")
                metrics["failed_starts_count"] += len(batch)

    except Exception as e:
        logger.error(f"Critical error during batch processing: {e}", exc_info=True)
        raise

    total_accounts_processed = (
        metrics["processed_count"]
        + metrics["failed_starts_count"]
        + metrics["skipped_count"]
        + metrics["already_exists_count"]
    )

    logger.info(
        f"MonthlyAccountReportsTrigger finished. Processed {total_accounts_processed} accounts in {metrics['batches_processed']} batches. Metrics: {metrics}"
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Monthly Account monthly_reports initiation complete",
                "totalAccountsProcessed": total_accounts_processed,
                **metrics,
            }
        ),
    }
