from dynamodb import get_paginated_table_data

from .metrics import merge_metrics, initialize_metrics
from .sfn import start_sfn_execution_with_retry
from .sqs import send_continuation_message, send_bad_account_to_dlq


def chunk_accounts(accounts, chunk_size=10):
    """
    Yield successive chunks of the input accounts list.

    Parameters:
        accounts (Sequence): Sequence of account items to split into chunks.
        chunk_size (int): Maximum size of each yielded chunk (default 10).

    Yields:
        list: Sublists of `accounts`, each with up to `chunk_size` items, in order.
    """
    for i in range(0, len(accounts), chunk_size):
        yield accounts[i : i + chunk_size]


def process_account_batch(
    accounts_batch,
    statement_period,
    sfn_client,
    logger,
    state_machine_arn,
    sqs_endpoint=None,
    dlq_url=None,
    aws_region=None,
):
    """
    Process a single batch of account records by validating each account and starting a Step Functions execution for valid entries.

    Each account in accounts_batch is validated for the presence of `accountId` and `userId`. Valid accounts are used to build a Step Functions input payload and an execution name derived from the statement period and accountId (truncated to 80 characters). Step Function executions are started with retry logic; results are tallied. Accounts with missing fields, failed starts, or exceptions are optionally sent to a dead-letter queue when dlq_url and aws_region are provided.

    Parameters:
        accounts_batch (list[dict]): List of account records; each dict should contain at least `accountId` and `userId`. Other optional fields used: `balance`.
        statement_period (str): Identifier for the statement period included in the SFN input and execution name.
        dlq_url (str | None): URL of the dead-letter queue. If provided together with aws_region, bad accounts and failures are sent to the DLQ.
        aws_region (str | None): AWS region used when sending messages to the DLQ. Required with dlq_url to enable DLQ handling.

    Returns:
        dict: Counts summarising the batch processing with keys:
            - "processed" (int): number of accounts for which SFN execution was started successfully.
            - "already_exists" (int): number of accounts skipped because an execution already existed.
            - "failed_starts" (int): number of accounts where starting the SFN execution failed or raised an exception.
            - "skipped" (int): number of accounts skipped due to missing required fields.
    """
    processed_count = 0
    skipped_count = 0
    already_exists_count = 0
    failed_starts_count = 0

    for account in accounts_batch:
        account_id = account.get("accountId")
        user_id = account.get("userId")

        if not all([account_id, user_id]):
            error_reason = (
                f"Missing required fields - accountId: {bool(account_id)}, "
                f"userId: {bool(user_id)}"
            )
            logger.warning(f"Skipping account with missing data: {account}")

            if dlq_url and aws_region:
                send_bad_account_to_dlq(
                    account,
                    statement_period,
                    error_reason,
                    sqs_endpoint,
                    dlq_url,
                    aws_region,
                    logger,
                )

            skipped_count += 1
            continue

        sf_input = {
            "accountId": account_id,
            "userId": user_id,
            "accountBalance": float(account.get("balance", 0)),
            "statementPeriod": statement_period,
        }

        base_name = f"Stmt-{statement_period}-{account_id}"
        execution_name = base_name[:80]

        try:
            result = start_sfn_execution_with_retry(
                sfn_client, state_machine_arn, execution_name, sf_input, logger
            )

            if result == "processed":
                processed_count += 1
            elif result == "already_exists":
                already_exists_count += 1
            else:
                failed_starts_count += 1
                if dlq_url and aws_region:
                    send_bad_account_to_dlq(
                        account,
                        statement_period,
                        f"Step Function execution failed: {result}",
                        sqs_endpoint,
                        dlq_url,
                        aws_region,
                        logger,
                    )

        except Exception as e:
            logger.error(f"Failed to start SF execution for account {account_id}: {e}")
            failed_starts_count += 1
            if dlq_url and aws_region:
                send_bad_account_to_dlq(
                    account,
                    statement_period,
                    f"Step Function execution exception: {str(e)}",
                    sqs_endpoint,
                    dlq_url,
                    aws_region,
                    logger,
                )

    return {
        "processed": processed_count,
        "already_exists": already_exists_count,
        "failed_starts": failed_starts_count,
        "skipped": skipped_count,
    }


def process_accounts_page(
    accounts_page,
    statement_period,
    context,
    logger,
    sfn_client,
    state_machine_arn,
    scan_params,
    last_evaluated_key,
    sqs_endpoint,
    continuation_queue_url,
    aws_region,
    batch_size=10,
    safety_buffer=30,
    dlq_url=None,
):
    """
    Process a single page of accounts by splitting it into batches and processing each batch.

    Parameters:
        accounts_page (list[dict]): List of account items retrieved from the accounts table. Each item is expected to be a mapping containing at least account identifiers and related fields used to start Step Functions executions.
        statement_period (str): Identifier for the statement period being processed (used to build SFN input and execution names).
        last_evaluated_key (dict | None): DynamoDB LastEvaluatedKey for the current page; passed through to batch-processing helpers for continuation logic.
        continuation_queue_url (str): SQS URL used to send continuation messages when processing must be resumed later.
        batch_size (int): Maximum number of accounts per batch when chunking the page. Defaults to 10.
        safety_buffer (int): Minimum remaining execution time in seconds required to start processing the next batch; if remaining time is below this, processing will send a continuation message and stop. Defaults to 30.
        dlq_url (str | None): Optional dead-letter queue URL — when provided, invalid accounts or failed starts are sent to this DLQ.

    Returns:
        dict: Aggregated metrics for the page (counts such as processed, already_exists, failed_starts, skipped, pages_processed, batches_processed, etc.).
    """
    metrics = initialize_metrics()

    account_batches = list(chunk_accounts(accounts_page, chunk_size=batch_size))
    logger.info(
        f"Processing {len(accounts_page)} accounts in {len(account_batches)} batches"
    )

    batch_metrics = process_account_batches(
        account_batches,
        statement_period,
        context,
        logger,
        sfn_client,
        state_machine_arn,
        scan_params,
        last_evaluated_key,
        sqs_endpoint,
        continuation_queue_url,
        aws_region,
        safety_buffer,
        dlq_url,
    )
    merge_metrics(metrics, batch_metrics)

    return metrics


def process_account_batches(
    account_batches,
    statement_period,
    context,
    logger,
    sfn_client,
    state_machine_arn,
    scan_params,
    last_evaluated_key,
    sqs_endpoint,
    continuation_queue_url,
    aws_region,
    safety_buffer=30,
    dlq_url=None,
):
    """
    Process multiple batches of accounts, starting Step Function executions for each account and aggregating metrics.

    This function iterates over account_batches and for each batch:
    - aborts and sends a single "batch_continuation" SQS message containing all remaining accounts if the Lambda remaining execution time falls below safety_buffer seconds;
    - otherwise calls process_account_batch for the batch, merges the returned counts into the running metrics (each returned key is added to metrics as '<key>_count'), and increments 'batches_processed';
    - on an exception while processing a batch, optionally sends each account in that batch to the DLQ (if dlq_url and aws_region are provided) with the exception as reason and increments 'failed_starts_count' by the batch size.

    Parameters that are self‑descriptive by name (logger, sfn_client, context, continuation_queue_url, etc.) are intentionally not documented here.

    Returns:
        dict: Aggregated metrics for the processed batches. Keys include counts suffixed with '_count' (e.g. 'processed_count', 'skipped_count', 'failed_starts_count') and 'batches_processed'.
    """
    metrics = initialize_metrics()

    for i, batch in enumerate(account_batches):
        remaining_time = context.get_remaining_time_in_millis() / 1000.0

        if remaining_time < safety_buffer:
            logger.warning("Timeout approaching during batch processing")

            remaining_batches = account_batches[i:]
            remaining_accounts = []
            for remaining_batch in remaining_batches:
                remaining_accounts.extend(remaining_batch)

            send_continuation_message(
                scan_params,
                statement_period,
                remaining_accounts,
                last_evaluated_key,
                "batch_continuation",
                sqs_endpoint,
                continuation_queue_url,
                aws_region,
                logger,
            )
            break

        try:
            logger.info(
                f"Processing batch {i + 1}/{len(account_batches)} with {len(batch)} accounts"
            )

            batch_result = process_account_batch(
                batch,
                statement_period,
                sfn_client,
                logger,
                state_machine_arn,
                sqs_endpoint,
                dlq_url,
                aws_region,
            )

            for key, value in batch_result.items():
                metrics_key = f"{key}_count"
                if metrics_key in metrics:
                    metrics[metrics_key] += value

            metrics["batches_processed"] += 1

        except Exception as e:
            logger.error(f"Error processing batch {i + 1}: {e}")
            if dlq_url and aws_region:
                for account in batch:
                    send_bad_account_to_dlq(
                        account,
                        statement_period,
                        f"Batch processing exception: {str(e)}",
                        sqs_endpoint,
                        dlq_url,
                        aws_region,
                        logger,
                    )
            metrics["failed_starts_count"] += len(batch)

    return metrics


def process_accounts_scan_continuation(
    scan_params,
    statement_period,
    context,
    logger,
    accounts_table,
    sfn_client,
    state_machine_arn,
    sqs_endpoint,
    continuation_queue_url,
    aws_region,
    page_size=50,
    batch_size=10,
    safety_buffer=30,
    dlq_url=None,
):
    """
    Continue a paginated scan of the accounts table and process each page, sending continuation messages if the Lambda is close to timing out.

    This function repeatedly retrieves pages of accounts from DynamoDB using `scan_params`, processes each page (splitting into batches and starting Step Function executions), merges per-page metrics into an aggregated metrics dictionary, and sends an SQS continuation message if the remaining Lambda execution time falls below `safety_buffer`. If a page returns a LastEvaluatedKey it is used to continue the scan; when there are no more pages the function finishes and returns aggregated metrics.

    Parameters:
        scan_params (dict): DynamoDB scan parameters; `ExclusiveStartKey` will be updated when pagination continues.
        statement_period (str): Identifier for the statement period being processed; used in continuation messages and Step Function input.
        page_size (int): Number of items to request per DynamoDB page (default 50).
        batch_size (int): Number of accounts to include per processing batch (default 10).
        safety_buffer (int|float): Minimum remaining seconds of Lambda execution time required to start processing another page; if the remaining time is below this value a continuation message is sent (default 30).
        dlq_url (str|None): Optional dead-letter queue URL; when provided invalid accounts or failed starts are sent to the DLQ.

    Returns:
        dict: Aggregated metrics describing work performed (e.g. pages_processed, processed_count, skipped_count, failed_starts_count, already_exists_count, batches_processed).
    """
    metrics = initialize_metrics()

    logger.info(f"Continuing scan for period: {statement_period}")

    while True:
        remaining_time = context.get_remaining_time_in_millis() / 1000.0
        if remaining_time < safety_buffer:
            logger.warning("Approaching timeout, sending continuation message")
            send_continuation_message(
                scan_params,
                statement_period,
                None,
                scan_params.get("ExclusiveStartKey"),
                "accounts_scan",
                sqs_endpoint,
                continuation_queue_url,
                aws_region,
                logger,
            )
            break

        accounts_page, last_evaluated_key = get_paginated_table_data(
            scan_params=scan_params,
            index_name=None,
            table=accounts_table,
            logger=logger,
            page_size=page_size,
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
            state_machine_arn,
            scan_params,
            last_evaluated_key,
            sqs_endpoint,
            continuation_queue_url,
            aws_region,
            batch_size,
            safety_buffer,
            dlq_url,
        )
        merge_metrics(metrics, page_metrics)

        if last_evaluated_key:
            scan_params["ExclusiveStartKey"] = last_evaluated_key
        else:
            logger.info("All pages processed successfully")
            break

    return metrics


def process_batch_continuation(
    scan_params,
    statement_period,
    remaining_accounts,
    last_evaluated_key,
    context,
    logger,
    accounts_table,
    sfn_client,
    state_machine_arn,
    sqs_endpoint,
    continuation_queue_url,
    aws_region,
    page_size=50,
    batch_size=10,
    safety_buffer=30,
    dlq_url=None,
):
    """
    Process any remaining account batches and, if provided, continue scanning the accounts table, returning aggregated metrics.

    Processes the provided remaining_accounts by chunking them into batches and invoking the batch processor. If last_evaluated_key is present, updates scan_params to continue the DynamoDB scan and processes subsequent pages. Metrics from batch processing and any continued scan are merged and returned.

    Parameters:
        scan_params (dict): DynamoDB scan parameters; will be updated with "ExclusiveStartKey" when continuing a scan.
        statement_period (str): Identifier for the reporting period used when starting Step Function executions.
        remaining_accounts (list): Accounts to process now (each item is the account record as returned from DynamoDB).
        last_evaluated_key (dict|None): DynamoDB ExclusiveStartKey to resume scanning from; if present the function continues the scan after processing remaining_accounts.

    Returns:
        dict: Aggregated metrics for processed batches and any continued scan (counts for processed, skipped, failed, pages/batches processed, etc.).
    """
    metrics = initialize_metrics()

    logger.info(f"Processing {len(remaining_accounts)} remaining accounts")

    if remaining_accounts:
        remaining_batches = list(
            chunk_accounts(remaining_accounts, chunk_size=batch_size)
        )
        batch_metrics = process_account_batches(
            remaining_batches,
            statement_period,
            context,
            logger,
            sfn_client,
            state_machine_arn,
            scan_params,
            last_evaluated_key,
            sqs_endpoint,
            continuation_queue_url,
            aws_region,
            safety_buffer,
            dlq_url,
        )
        merge_metrics(metrics, batch_metrics)

    if last_evaluated_key:
        scan_params["ExclusiveStartKey"] = last_evaluated_key
        scan_metrics = process_accounts_scan_continuation(
            scan_params,
            statement_period,
            context,
            logger,
            accounts_table,
            sfn_client,
            state_machine_arn,
            sqs_endpoint,
            continuation_queue_url,
            aws_region,
            page_size,
            batch_size,
            safety_buffer,
            dlq_url,
        )
        merge_metrics(metrics, scan_metrics)

    return metrics
