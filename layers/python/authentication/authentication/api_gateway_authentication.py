from aws_lambda_powertools.event_handler.exceptions import (
    UnauthorizedError,
    InternalServerError,
)

from .exceptions import (
    MissingSubClaimError,
    InvalidTokenError,
    AuthConfigurationError,
    AuthVerificationError,
)
from .id_extraction import get_sub_from_id_token


def authenticate_user(
    event, headers, cognito_user_pool_id, cognito_client_id, aws_region, logger
):
    """
    Authenticates a user by extracting and verifying their identity from a Lambda event or HTTP headers.

    Attempts to retrieve the user ID (`sub` claim) from the event's authorizer claims. If not present, checks for an authorisation header, verifies the JWT ID token using AWS Cognito, and extracts the user ID. Returns a tuple containing the user ID and `None` on success, or `None` and an HTTP response object on failure. Responds with appropriate status codes and error messages for missing or invalid tokens, configuration errors, or unexpected authentication failures.
    """
    if (
        "requestContext" in event
        and "authorizer" in event["requestContext"]
        and "claims" in event["requestContext"]["authorizer"]
    ):
        user_id = event["requestContext"]["authorizer"]["claims"].get("sub")
        if user_id:
            return user_id, None

    if "authorization" in headers:
        try:
            bearer = headers["authorization"]
            token = (
                bearer.split(" ", 1)[-1]
                if bearer.lower().startswith("bearer ")
                else bearer
            )

            user_id = get_sub_from_id_token(
                token,
                cognito_user_pool_id,
                cognito_client_id,
                aws_region,
                logger,
            )

            return user_id, None

        except (MissingSubClaimError, InvalidTokenError) as e:
            logger.warning(f"Authentication failed (Invalid Token/Claims): {e}")
            return None, UnauthorizedError(
                f"Unauthorized: Invalid authentication token ({e})"
            )
        except AuthConfigurationError as e:
            logger.critical(f"Authentication configuration error: {e}", exc_info=True)
            return None, InternalServerError(
                "Server authentication configuration error. Please contact support."
            )
        except AuthVerificationError as e:
            logger.error(
                f"Generic authentication verification error: {e}", exc_info=True
            )
            return None, InternalServerError(
                "Internal authentication error. Please contact support."
            )
        except Exception as e:
            logger.exception(f"Unexpected error during direct token verification: {e}")
            return None, InternalServerError(
                "An unexpected error occurred during authentication.",
            )

    logger.error("Failed to determine user ID after all attempts.")
    return None, UnauthorizedError(
        "Unauthorized: User identity could not be determined. Please ensure a valid token is provided."
    )
