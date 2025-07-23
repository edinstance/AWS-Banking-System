from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

from .api_gateway_authentication import authenticate_user


def authenticate_request(
    event, headers, cognito_user_pool_id, cognito_client_id, aws_region, logger
):
    """
    Authenticate an incoming request using AWS Cognito and return the authenticated user's ID.

    Attempts to authenticate the request with the provided event, headers, Cognito user pool ID, client ID, and AWS region. Raises an authentication error if authentication fails or if the user identity cannot be determined.

    Returns:
        str: The authenticated user's ID.

    Raises:
        Exception: If authentication fails or the user identity cannot be determined.
    """
    user_id, auth_error = authenticate_user(
        event.raw_event,
        headers,
        cognito_user_pool_id,
        cognito_client_id,
        aws_region,
        logger,
    )

    if auth_error:
        raise auth_error

    if not user_id:
        logger.error("Authentication failed: No user ID returned")
        raise UnauthorizedError("Unauthorized: User identity could not be determined")

    return user_id
