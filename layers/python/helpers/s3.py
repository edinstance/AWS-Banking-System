from logging import Logger

import boto3


def get_s3_client(aws_region: str, logger: Logger):
    try:
        client = boto3.client("s3", region_name=aws_region)
        logger.info("Initialized S3 client with default endpoint")
        return client
    except Exception:
        logger.error("Failed to initialize S3 client", exc_info=True)
        raise
