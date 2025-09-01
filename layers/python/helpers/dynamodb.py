import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError


def get_dynamodb_resource(dynamodb_endpoint: str, aws_region: str, logger: Logger):
    """
    Initialise and return a boto3 DynamoDB ServiceResource for the given region, optionally using a custom endpoint URL.
    
    If `dynamodb_endpoint` is provided it will be used as the resource's `endpoint_url`; otherwise the default AWS endpoint is used. Any exception raised during resource creation is propagated.
    
    Parameters:
        dynamodb_endpoint (str): Custom DynamoDB endpoint URL; pass an empty string or None to use the default AWS endpoint.
        aws_region (str): AWS region name to configure the resource.
    
    Returns:
        boto3.resources.factory.dynamodb.ServiceResource: Configured DynamoDB service resource.
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
    """
    Scan a DynamoDB table page and return the items plus the pagination key.
    
    Performs a single paginated scan against the provided DynamoDB Table resource using
    the given scan parameters and optional index, limiting results to `page_size`.
    
    Parameters:
        scan_params (dict | None): Additional parameters to pass to `Table.scan`. If None,
            an empty dict is used. The function will copy and set the `Limit` key.
        index_name (str | None): Optional DynamoDB index name to include as `IndexName`.
        page_size (int): Maximum number of items to return for this page (sets `Limit`).
    
    Returns:
        tuple[list, dict | None]: A tuple of (items, last_evaluated_key). `items` is a list
        of returned items (empty list if none). `last_evaluated_key` is the pagination key
        to use for the next scan, or None if there are no further pages.
    
    Raises:
        botocore.exceptions.ClientError: Propagates any ClientError raised by the DynamoDB scan.
    """
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
