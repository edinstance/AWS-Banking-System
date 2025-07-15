import boto3
from aws_lambda_powertools import Logger


def get_dynamodb_resource(dynamodb_endpoint: str, aws_region: str, logger: Logger):
    """
    Initialises and returns a boto3 DynamoDB resource for a given AWS region, optionally using a custom endpoint URL.
    
    Parameters:
        dynamodb_endpoint (str): Custom DynamoDB endpoint URL. If empty, the default AWS endpoint is used.
        aws_region (str): AWS region in which to initialise the DynamoDB resource.
    
    Returns:
        DynamoDB ServiceResource: A boto3 DynamoDB resource instance configured for the specified region and endpoint.
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
