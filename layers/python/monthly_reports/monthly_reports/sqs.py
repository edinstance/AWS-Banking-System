import datetime
from typing import Optional, Dict, Any, List

from aws_lambda_powertools import Logger

from sqs import send_message_to_sqs


def send_continuation_message(
    scan_params: Dict[str, Any],
    statement_period: str,
    remaining_accounts: Optional[List[Dict[str, Any]]],
    last_evaluated_key: Optional[Dict[str, Any]],
    continuation_type: str,
    sqs_endpoint: str,
    continuation_queue_url: str,
    aws_region: str,
    logger: Logger,
):
    """Send continuation message to SQS"""
    if not continuation_queue_url:
        logger.error("Cannot send continuation message: CONTINUATION_QUEUE_URL not set")
        return

    message_body: Dict[str, Any] = {
        "scan_params": scan_params,
        "statement_period": statement_period,
    }

    if remaining_accounts:
        message_body["remaining_accounts"] = remaining_accounts
    if last_evaluated_key:
        message_body["last_evaluated_key"] = last_evaluated_key

    message_attributes = {
        "continuation_type": {
            "DataType": "String",
            "StringValue": continuation_type,
        }
    }

    send_message_to_sqs(
        message=message_body,
        message_attributes=message_attributes,
        sqs_endpoint=sqs_endpoint,
        sqs_url=continuation_queue_url,
        aws_region=aws_region,
        logger=logger,
    )


def send_bad_account_to_dlq(
    account: Dict[str, Any],
    statement_period: str,
    error_reason: str,
    sqs_endpoint: str,
    dlq_url: str,
    aws_region: str,
    logger: Logger,
):
    """Send bad account to DLQ"""
    if not dlq_url:
        logger.warning("Cannot send bad account to DLQ: DLQ_URL not set")
        return

    message_body = {
        "account": account,
        "statement_period": statement_period,
        "error_reason": error_reason,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    }

    message_attributes = {
        "error_type": {
            "DataType": "String",
            "StringValue": "bad_account",
        },
        "error_reason": {
            "DataType": "String",
            "StringValue": error_reason,
        },
    }

    try:
        send_message_to_sqs(
            message=message_body,
            message_attributes=message_attributes,
            sqs_endpoint=sqs_endpoint,
            sqs_url=dlq_url,
            aws_region=aws_region,
            logger=logger,
        )
        logger.info(
            f"Sent bad account to DLQ: {account.get('accountId', 'unknown')} - {error_reason}"
        )
    except Exception as e:
        logger.error(f"Failed to send bad account to DLQ: {e}")
