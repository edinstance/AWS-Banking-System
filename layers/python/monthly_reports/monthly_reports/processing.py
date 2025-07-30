from dynamodb import get_paginated_table_data

from .metrics import merge_metrics, initialize_metrics
from .sfn import start_sfn_execution_with_retry
from .sqs import send_continuation_message, send_bad_account_to_dlq


def chunk_accounts(accounts, chunk_size=10):
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
    valid_accounts = []
    skipped_count = 0

    for account in accounts_batch:
        account_id = account.get("accountId")
        user_id = account.get("userId")

        if not all([account_id, user_id]):
            error_reason = f"Missing required fields - accountId: {bool(account_id)}, userId: {bool(user_id)}"
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

        valid_accounts.append(
            {
                "accountId": account_id,
                "userId": user_id,
                "statementPeriod": statement_period,
            }
        )

    if not valid_accounts:
        logger.warning("No valid accounts in batch to process")
        return {"skipped": skipped_count}

    sf_input = {
        "accounts": valid_accounts,
        "statementPeriod": statement_period,
        "batchSize": len(valid_accounts),
    }

    account_ids = [
        acc["accountId"][:5] if len(acc["accountId"]) >= 5 else acc["accountId"]
        for acc in valid_accounts[:3]
    ]
    execution_name = f"StmtBatch-{statement_period}-{'-'.join(account_ids)}"[:80]

    try:
        result = start_sfn_execution_with_retry(
            sfn_client, state_machine_arn, execution_name, sf_input, logger
        )

        if result == "processed":
            return {"processed": len(valid_accounts), "skipped": skipped_count}
        elif result == "already_exists":
            return {"already_exists": len(valid_accounts), "skipped": skipped_count}
        else:
            if dlq_url and aws_region:
                for account in valid_accounts:
                    send_bad_account_to_dlq(
                        account,
                        statement_period,
                        f"Step Function execution failed: {result}",
                        sqs_endpoint,
                        dlq_url,
                        aws_region,
                        logger,
                    )
            return {"failed_starts": len(valid_accounts), "skipped": skipped_count}

    except Exception as e:
        logger.error(f"Failed to start SF execution for batch: {e}")
        if dlq_url and aws_region:
            for account in valid_accounts:
                send_bad_account_to_dlq(
                    account,
                    statement_period,
                    f"Step Function execution exception: {str(e)}",
                    sqs_endpoint,
                    dlq_url,
                    aws_region,
                    logger,
                )
        return {"failed_starts": len(valid_accounts), "skipped": skipped_count}


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
    """Process multiple batches of accounts"""
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
