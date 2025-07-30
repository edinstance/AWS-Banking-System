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


def send_message_to_sqs(
    message: dict,
    message_attributes: dict,
    sqs_endpoint: str,
    sqs_url: str,
    aws_region: str,
    logger: Logger,
):
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
