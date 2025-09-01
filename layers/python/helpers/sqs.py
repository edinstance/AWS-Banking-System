import json

import boto3
from aws_lambda_powertools import Logger


def get_sqs_client(sqs_endpoint: str, aws_region: str, logger: Logger):
    """
    Initialise and return a boto3 SQS client for the given AWS region and optional custom endpoint.
    
    If sqs_endpoint is provided the client is created with that endpoint_url; otherwise the default AWS endpoint for the region is used.
    
    Parameters:
        sqs_endpoint (str): Custom SQS endpoint URL, or falsy to use the default endpoint.
        aws_region (str): AWS region name for the SQS client.
    
    Returns:
        boto3.client: An SQS client configured for the specified region/endpoint.
    
    Raises:
        Exception: Re-raises any exception raised while creating the boto3 client.
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


def send_message_to_sqs(
    message: dict,
    message_attributes: dict,
    sqs_endpoint: str,
    sqs_url: str,
    aws_region: str,
    logger: Logger,
):
    """
    Send a JSON-serialised message with attributes to an Amazon SQS queue.
    
    The provided `message` is serialised to JSON and sent to the queue identified by `sqs_url`. If `sqs_endpoint` is supplied a client is initialised against that endpoint; otherwise the default AWS SQS endpoint for `aws_region` is used. The function logs failures and returns a boolean status rather than raising.
    
    Parameters:
        message (dict): Payload to send; will be JSON-serialised for the SQS MessageBody.
        message_attributes (dict): Optional SQS MessageAttributes mapping (e.g. {"attr": {"StringValue": "value", "DataType": "String"}}).
        sqs_endpoint (str): Optional custom SQS endpoint URL (e.g. for local testing).
        sqs_url (str): Full SQS QueueUrl to which the message will be sent.
        aws_region (str): AWS region name used when creating the SQS client.
    
    Returns:
        bool: True if the message was successfully sent; False if preconditions fail or sending fails.
    """
    if not sqs_url:
        logger.error("SQS URL not configured, cannot send message to DLQ")
        return False

    if not message:
        logger.error("Message is required to send to SQS")
        return False

    sqs_client = get_sqs_client(
        sqs_endpoint=sqs_endpoint, aws_region=aws_region, logger=logger
    )

    try:
        sqs_client.send_message(
            QueueUrl=sqs_url,
            MessageBody=json.dumps(message),
            MessageAttributes=message_attributes,
        )

        logger.info("Successfully sent message to SQS queue.")
        return True

    except Exception as e:
        logger.error(f"Failed to send message to SQS: {e}")
        return False
