"""
Authentication module for the Record Transactions Lambda function.
"""

import os

import jwt
from aws_lambda_powertools import Logger
from jwt import PyJWKClient
from jwt.exceptions import (
    PyJWTError,
    InvalidAudienceError,
    InvalidIssuerError,
    ExpiredSignatureError,
)

from .exceptions import (
    MissingSubClaimError,
    InvalidTokenError,
    AuthConfigurationError,
    AuthVerificationError,
)
from .helpers import create_response

POWERTOOLS_LOG_LEVEL = os.environ.get("POWERTOOLS_LOG_LEVEL", "INFO").upper()
logger = Logger(service="RecordTransactionAuth", level=POWERTOOLS_LOG_LEVEL)


def get_sub_from_id_token(
    id_token: str, user_pool_id: str, client_id: str, aws_region: str
) -> str:
    """
    Verifies an AWS Cognito JWT ID token and returns the user's unique identifier.
    
    Validates the token's signature, audience, issuer, and ensures it is an ID token. Extracts and returns the 'sub' claim, which uniquely identifies the user.
    
    Raises:
        AuthConfigurationError: If the Cognito User Pool ID or Client ID is invalid, or if JWKS retrieval fails.
        InvalidTokenError: If the token is expired, has an invalid audience or issuer, is not an ID token, or fails verification.
        MissingSubClaimError: If the 'sub' claim is not present in the token.
        AuthVerificationError: For unexpected authentication errors.
        
    Returns:
        The value of the 'sub' claim from the verified token.
    """
    if not user_pool_id or not isinstance(user_pool_id, str):
        raise AuthConfigurationError("Invalid or missing Cognito User Pool ID")
    if not client_id or not isinstance(client_id, str):
        raise AuthConfigurationError("Invalid or missing Cognito Client ID")

    try:
        jwks_url = f"https://cognito-idp.{aws_region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
        jwks_client = PyJWKClient(jwks_url)
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(id_token)

        except PyJWTError as e:
            logger.error(f"Failed to fetch or process JWKS: {str(e)}")
            raise AuthConfigurationError(
                "Auth configuration error: Failed to fetch or process JWKS"
            ) from e

        except Exception as e:
            logger.error(f"Failed to fetch or process JWKS: {str(e)}")
            raise AuthVerificationError(
                "An unexpected authentication error occurred"
            ) from e

        payload = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=f"https://cognito-idp.{aws_region}.amazonaws.com/{user_pool_id}",
        )

        if "sub" not in payload:
            raise MissingSubClaimError("Token is missing the 'sub' claim")

        if payload.get("token_use") != "id":
            raise InvalidTokenError("Token is not an ID token")

        return payload["sub"]

    except (InvalidAudienceError, InvalidIssuerError) as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise InvalidTokenError(str(e)) from e
    except ExpiredSignatureError:
        logger.error("Token has expired")
        raise InvalidTokenError("Token has expired")
    except PyJWTError as e:
        logger.error(f"JWT verification failed: {str(e)}")
        raise InvalidTokenError(f"JWT processing failed: {str(e)}") from e
    except MissingSubClaimError:
        raise
    except InvalidTokenError:
        raise
    except AuthConfigurationError:
        raise
    except Exception as e:
        logger.error(f"Unexpected authentication error: {str(e)}")
        raise AuthVerificationError(
            "An unexpected authentication error occurred"
        ) from e


def authenticate_user(
    event, headers, cognito_user_pool_id, cognito_client_id, aws_region
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
            )

            if not user_id:
                return None, create_response(
                    401,
                    {
                        "error": "Unauthorized: User identity could not be determined. Please ensure a valid token is provided."
                    },
                    "OPTIONS,POST",
                )

            return user_id, None

        except (MissingSubClaimError, InvalidTokenError) as e:
            logger.warning(f"Authentication failed (Invalid Token/Claims): {e}")
            return None, create_response(
                401,
                {"error": f"Unauthorized: Invalid authentication token ({e})"},
                "OPTIONS,POST",
            )
        except AuthConfigurationError as e:
            logger.critical(f"Authentication configuration error: {e}", exc_info=True)
            return None, create_response(
                500,
                {
                    "error": "Server authentication configuration error. Please contact support."
                },
                "OPTIONS,POST",
            )
        except AuthVerificationError as e:
            logger.error(
                f"Generic authentication verification error: {e}", exc_info=True
            )
            return None, create_response(
                500,
                {"error": "Internal authentication error. Please contact support."},
                "OPTIONS,POST",
            )
        except Exception as e:
            logger.exception(f"Unexpected error during direct token verification: {e}")
            return None, create_response(
                500,
                {"error": "An unexpected error occurred during authentication."},
                "POST",
            )

    logger.error(f"Failed to determine user ID after all attempts. Event: {event}")
    return None, create_response(
        401,
        {
            "error": "Unauthorized: User identity could not be determined. Please ensure a valid token is provided."
        },
        "OPTIONS,POST",
    )
