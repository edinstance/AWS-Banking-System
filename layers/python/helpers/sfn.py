import boto3
from aws_lambda_powertools import Logger


def get_sfn_client(aws_region: str, logger: Logger):
    """
    Create and return a boto3 AWS Step Functions (SFN) client for the given region.

    Parameters:
        aws_region (str): AWS region name (e.g. 'eu-west-1') used to configure the client.

    Returns:
        boto3.client: A configured Step Functions client.

    Raises:
        Exception: Re-raises any exception encountered while creating the client.
    """
    try:
        client = boto3.client("stepfunctions", region_name=aws_region)
        logger.info("Initialized SFN client with default endpoint")
        return client
    except Exception:
        logger.error("Failed to initialize SFN client", exc_info=True)
        raise
