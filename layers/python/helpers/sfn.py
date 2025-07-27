import boto3
from aws_lambda_powertools import Logger


def get_sfn_client(aws_region: str, logger: Logger):
    try:
        client = boto3.client("stepfunctions", region_name=aws_region)
        logger.debug("Initialized SFN client")
        return client
    except Exception:
        logger.error("Failed to initialize SFN client", exc_info=True)
        raise
