import boto3
from aws_lambda_powertools import Logger


def get_user_attributes(
    aws_region: str, logger: Logger, username: str, user_pool_id: str
) -> dict:
    """
    Fetch Cognito user attributes for a given username in a specified user pool.
    
    Calls Cognito Identity Provider's AdminGetUser for the provided user pool and username,
    and returns a dict mapping attribute names to their values.
    
    Parameters:
        aws_region (str): AWS region where the Cognito user pool resides.
        username (str): Username (or sub) of the Cognito user to retrieve.
        user_pool_id (str): ID of the Cognito user pool.
    
    Returns:
        dict: Mapping of attribute names to attribute values (e.g. {"email": "user@example.com"}).
    
    Raises:
        Exception: Propagates any exception raised by the Cognito client (e.g. client errors when the user or pool is not found).
    """
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
