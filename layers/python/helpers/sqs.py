import json

import boto3
from aws_lambda_powertools import Logger


def get_sqs_client(sqs_endpoint: str, aws_region: str, logger: Logger):
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
    sqs_url: str,
    dlq_url: str,
    aws_region: str,
    error_message: str,
    logger: Logger,
):
    if not dlq_url:
        logger.error("DLQ URL not configured, cannot send message to DLQ")
        return False

    sqs_client = get_sqs_client(
        sqs_endpoint=sqs_url, aws_region=aws_region, logger=logger
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
