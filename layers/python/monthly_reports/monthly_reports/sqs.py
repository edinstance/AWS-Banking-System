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
    """
    Send a continuation message to an SQS queue for resuming a paginated scan.

    The function constructs a JSON message containing the provided scan parameters and statement period and conditionally includes remaining_accounts and last_evaluated_key when present. The message is sent to the queue identified by continuation_queue_url with a message attribute named `continuation_type`.

    Parameters:
        scan_params (Dict[str, Any]): Scan configuration/state required to continue processing.
        statement_period (str): Identifier for the statement period this message relates to.
        remaining_accounts (Optional[List[Dict[str, Any]]]): Optional list of accounts yet to be processed; included in the message only if truthy.
        last_evaluated_key (Optional[Dict[str, Any]]): Optional DynamoDB pagination key to resume a scan; included only if truthy.
        continuation_type (str): Short string describing the reason or category of the continuation (set as the message attribute `continuation_type`).

    Notes:
        If continuation_queue_url is not provided the function logs an error and returns without sending.
    """
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
    """
    Send information about a failing account to the configured dead‑letter SQS queue.

    Builds a message containing the provided account data, statement period, error reason and a UTC ISO timestamp, and sends it to the DLQ URL. If dlq_url is falsy the function returns without sending. Any exception raised while sending is caught and logged; the function does not re-raise.

    Parameters:
        account (Dict[str, Any]): Account payload to include in the message (may contain an 'accountId' key).
        statement_period (str): Identifier for the statement period this error relates to.
        error_reason (str): Short description of why the account is considered bad.
        dlq_url (str): Full SQS queue URL for the dead‑letter queue.
        aws_region (str): AWS region to use when sending the message.

    Note:
        The `sqs_endpoint` and `logger` parameters are service utilities and are not documented here.
    """
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
