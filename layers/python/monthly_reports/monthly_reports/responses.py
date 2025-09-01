from aws_lambda_powertools import Logger


def create_response(metrics, status, logger: Logger):
    """
    Create a standardized HTTP-like response dictionary summarising monthly account report processing.
    
    Calculates the total accounts processed from the supplied `metrics` and returns a dict with a numeric `statusCode`
    (mapped from `status`) and a `body` containing a human-readable message, the original `status`, the computed
    `totalAccountsProcessed`, and all metric entries merged in.
    
    Parameters:
        metrics (dict): Counters expected to include the integer keys
            "processed_count", "failed_starts_count", "skipped_count", and "already_exists_count".
        status (str): Processing status string; specific values are mapped to status codes
            ("COMPLETED" -> 200, "TIMEOUT_CONTINUATION" -> 202, "ERROR_NO_CONTINUATION_QUEUE" and "CRITICAL_ERROR" -> 500).
            Unknown statuses default to 500.
    
    Returns:
        dict: Response with keys:
            - "statusCode" (int): HTTP-like status code determined from `status`.
            - "body" (dict): Contains "message", "status", "totalAccountsProcessed" and all entries from `metrics`.
    
    Note:
        A logger instance is used for informational logging but is not documented as a parameter here.
    """
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
