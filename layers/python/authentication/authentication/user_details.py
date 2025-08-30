import boto3
from aws_lambda_powertools import Logger


def get_user_attributes(
    aws_region: str, logger: Logger, username: str, user_pool_id: str
) -> dict:
    try:
        cognito = boto3.client("cognito-idp", region_name=aws_region)

        response = cognito.admin_get_user(
            UserPoolId=user_pool_id,
            Username=username,
        )
        attrs = {attr["Name"]: attr["Value"] for attr in response["UserAttributes"]}
        logger.info(f"Fetched attributes for user: {username}.")
        return attrs
    except Exception as e:
        logger.exception(f"Failed to fetch user {username} from Cognito")
        raise e
