from logging import Logger

import boto3


def get_s3_client(aws_region: str, logger: Logger):
    """
    Create and return a boto3 S3 client configured for the given AWS region.

    Parameters:
        aws_region (str): AWS region name used to configure the S3 client.

    Returns:
        boto3 S3 client: A configured S3 client instance.

    Raises:
        Exception: Propagates any exception raised while initializing the client.
    """
    try:
        client = boto3.client("s3", region_name=aws_region)
        logger.info("Initialized S3 client with default endpoint")
        return client
    except Exception:
        logger.error("Failed to initialize S3 client", exc_info=True)
        raise
