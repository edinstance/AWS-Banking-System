import json

import boto3
from aws_lambda_powertools import Logger


def get_sqs_client(sqs_endpoint: str, aws_region: str, logger: Logger):
    """
    Initialises and returns a boto3 SQS client for the specified AWS region and optional custom endpoint.

    Parameters:
        sqs_endpoint (str): Custom SQS endpoint URL. If not provided, the default AWS endpoint is used.
        aws_region (str): AWS region for the SQS client.

    Returns:
        boto3 SQS client instance.
    """
    try:
        if sqs_endpoint:
            logger.debug(f"Initialized SQS client with endpoint {sqs_endpoint}")
            return boto3.client(
                "sqs", endpoint_url=sqs_endpoint, region_name=aws_region
            )
        logger.debug("Initialized SQS client with default endpoint")
        return boto3.client("sqs", region_name=aws_region)
    except Exception:
        logger.error("Failed to initialize SQS client", exc_info=True)
        raise


def send_dynamodb_record_to_dlq(
    record: dict,
    sqs_endpoint: str,
    dlq_url: str,
    aws_region: str,
    error_message: str,
    logger: Logger,
):
    """
    Send a DynamoDB stream record to an SQS Dead Letter Queue (DLQ).

    If the DLQ URL is not provided, logs an error and returns False. Constructs a message containing the original record, an error message, and relevant metadata, then sends it to the specified DLQ. Returns True if the message is sent successfully, otherwise logs the failure and returns False.

    Parameters:
        record (dict): The DynamoDB stream record to send.
        sqs_endpoint (str): Optional custom SQS endpoint URL.
        dlq_url (str): The URL of the SQS Dead Letter Queue.
        aws_region (str): AWS region for the SQS client.
        error_message (str): Description of the error that triggered the DLQ send.

    Returns:
        bool: True if the message was sent successfully, False otherwise.
    """
    if not dlq_url:
        logger.error("DLQ URL not configured, cannot send message to DLQ")
        return False

    sqs_client = get_sqs_client(
        sqs_endpoint=sqs_endpoint, aws_region=aws_region, logger=logger
    )

    try:
        dlq_message = {
            "originalRecord": record,
            "errorMessage": error_message,
            "timestamp": record.get("dynamodb", {}).get("ApproximateCreationDateTime"),
            "sequenceNumber": record.get("dynamodb", {}).get("SequenceNumber"),
        }

        sqs_client.send_message(
            QueueUrl=dlq_url,
            MessageBody=json.dumps(dlq_message),
            MessageAttributes={
                "ErrorType": {"StringValue": "SystemError", "DataType": "String"}
            },
        )

        logger.info(
            f"Successfully sent record to DLQ: {record.get('dynamodb', {}).get('SequenceNumber')}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to send message to DLQ: {e}")
        return False
