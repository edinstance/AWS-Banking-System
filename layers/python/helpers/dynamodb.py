import boto3
from aws_lambda_powertools import Logger


def get_dynamodb_resource(dynamodb_endpoint: str, aws_region: str, logger: Logger):
    """
    Creates and returns a boto3 DynamoDB resource for the specified AWS region, optionally using a custom endpoint URL.

    If a custom endpoint is provided, the DynamoDB resource is configured to use it; otherwise, the default AWS endpoint is used.

    Args:
        dynamodb_endpoint: Custom DynamoDB endpoint URL. If not provided, the default AWS endpoint is used.
        aws_region: AWS region in which to initialise the DynamoDB resource.
        logger: Logger instance to use.

    Returns:
        A boto3 DynamoDB resource instance.
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
