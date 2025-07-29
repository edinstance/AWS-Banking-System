import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError


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


def get_paginated_table_data(
    scan_params, index_name, table, logger: Logger, page_size: int = 10
):
    if scan_params is None:
        scan_params = {}

    scan_params = scan_params.copy()
    scan_params["Limit"] = page_size

    if index_name:
        scan_params["IndexName"] = index_name

    try:
        response = table.scan(**scan_params)
        items = response.get("Items", [])
        last_evaluated_key = response.get("LastEvaluatedKey")

        logger.info(f"Fetched {len(items)} items from DynamoDB")

        return items, last_evaluated_key

    except ClientError as exception:
        logger.error(f"Error during DynamoDB scan: {exception}", exc_info=True)
        raise exception
