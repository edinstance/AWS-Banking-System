from aws_lambda_powertools import Logger


def create_response(metrics, status, logger: Logger):
    total_accounts_processed = (
        metrics["processed_count"]
        + metrics["failed_starts_count"]
        + metrics["skipped_count"]
        + metrics["already_exists_count"]
    )

    logger.info(
        f"Processing finished with status: {status}. "
        f"Processed {total_accounts_processed} accounts. "
        f"Metrics: {metrics}"
    )

    if status in ["ERROR_NO_CONTINUATION_QUEUE", "CRITICAL_ERROR"]:
        status_code = 500
    elif status in ["TIMEOUT_CONTINUATION"]:
        status_code = 202
    elif status == "COMPLETED":
        status_code = 200
    else:
        status_code = 500

    return {
        "statusCode": status_code,
        "body": {
            "message": f"Monthly Account reports processing {status.lower()}",
            "status": status,
            "totalAccountsProcessed": total_accounts_processed,
            **metrics,
        },
    }
