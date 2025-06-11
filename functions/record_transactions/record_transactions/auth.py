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

POWERTOOLS_LOG_LEVEL = os.environ.get("POWERTOOLS_LOG_LEVEL", "INFO").upper()
logger = Logger(service="RecordTransactionAuth", level=POWERTOOLS_LOG_LEVEL)


def get_sub_from_id_token(
    id_token: str, user_pool_id: str, client_id: str, aws_region: str
) -> str:
    """
    Verifies a JWT ID token and extracts the 'sub' claim.

    Args:
        id_token: The JWT ID token to verify
        user_pool_id: The Cognito User Pool ID
        client_id: The Cognito Client ID
        aws_region: The AWS region where the User Pool is located

    Returns:
        The 'sub' claim from the verified token

    Raises:
        AuthConfigurationError: If there's an issue with the auth configuration
        InvalidTokenError: If the token is invalid, expired, or has wrong audience/issuer
        MissingSubClaimError: If the 'sub' claim is missing from the token
        AuthVerificationError: For unexpected authentication errors
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
