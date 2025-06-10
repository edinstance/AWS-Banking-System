import boto3
from aws_lambda_powertools import Logger


def get_dynamodb_resource(dynamodb_endpoint: str, aws_region: str, logger: Logger):
    """
    Initialize a DynamoDB resource with optional endpoint configuration.

    Args:
        dynamodb_endpoint: Optional custom endpoint URL for DynamoDB
        aws_region: AWS region to use
        logger: Logger instance for recording operations

    Returns:
        A boto3 DynamoDB resource
    """
    try:
        if dynamodb_endpoint:
            logger.debug(
                f"Initialized DynamoDB resource with endpoint {dynamodb_endpoint}"
            )
            return boto3.resource(
                "dynamodb", endpoint_url=dynamodb_endpoint, region_name=aws_region
            )
        logger.debug("Initialized DynamoDB resource with default endpoint")
        return boto3.resource("dynamodb", region_name=aws_region)
    except Exception:
        logger.error("Failed to initialize DynamoDB resource", exc_info=True)
        raise
