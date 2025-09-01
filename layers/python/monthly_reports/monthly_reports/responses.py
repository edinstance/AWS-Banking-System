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

    status_code_map = {
        "ERROR_NO_CONTINUATION_QUEUE": 500,
        "CRITICAL_ERROR": 500,
        "TIMEOUT_CONTINUATION": 202,
        "COMPLETED": 200,
    }

    status_code = status_code_map.get(status, 500)

    return {
        "statusCode": status_code,
        "body": {
            "message": f"Monthly Account reports processing {status.lower()}",
            "status": status,
            "totalAccountsProcessed": total_accounts_processed,
            **metrics,
        },
    }
