import threading
from typing import Dict, Any

import boto3
from aws_lambda_powertools import Logger

from authentication.exceptions import AuthConfigurationError
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
    UnauthorizedError,
    InternalServerError,
)
from .config import AuthConfig


class AuthService:
    def __init__(self, config: AuthConfig, cognito_client=None):
        """
        Initialises the AuthService with configuration, logging, and a Cognito client.

        If no Cognito client is provided, a default boto3 Cognito IDP client is created.
        """

        if (
            config.user_pool_id is None
            or config.cognito_client_id is None
            or config.user_pool_id == ""
            or config.cognito_client_id == ""
        ):
            raise AuthConfigurationError()

        self.config = config
        self.logger = Logger(service="AuthLambda", level=config.log_level)
        self.cognito_client = cognito_client or boto3.client("cognito-idp")

    def handle_login(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Authenticates a user with AWS Cognito and returns authentication tokens.
        
        Validates that both username and password are present in the request body, then attempts to authenticate the user using Cognito's ADMIN_USER_PASSWORD_AUTH flow. On success, returns a dictionary containing authentication tokens and expiry information. Raises HTTP exceptions for missing credentials, invalid login, unconfirmed users, non-existent users, rate limiting, or unexpected errors.
        
        Parameters:
            request_body (Dict[str, Any]): Dictionary containing 'username' and 'password' keys.
        
        Returns:
            Dict[str, Any]: Dictionary with authentication tokens and a success message.
        """
        username = request_body.get("username")
        password = request_body.get("password")

        if not username or not password:
            self.logger.warning("Missing username or password for login.")
            raise BadRequestError("Username and password are required.")

        try:
            auth_response = self.cognito_client.admin_initiate_auth(
                AuthFlow="ADMIN_USER_PASSWORD_AUTH",
                ClientId=self.config.cognito_client_id,
                AuthParameters={
                    "USERNAME": username,
                    "PASSWORD": password,
                },
                UserPoolId=self.config.user_pool_id,
            )
            self.logger.info(f"Successfully initiated auth for user: {username}")

            auth_result = auth_response.get("AuthenticationResult", {})
            return {
                "message": "Login successful!",
                "idToken": auth_result.get("IdToken"),
                "accessToken": auth_result.get("AccessToken"),
                "refreshToken": auth_result.get("RefreshToken"),
                "expiresIn": auth_result.get("ExpiresIn"),
            }

        except self.cognito_client.exceptions.NotAuthorizedException:
            self.logger.warning(
                f"Authentication failed for user: {username} (Invalid credentials)."
            )
            raise UnauthorizedError("Invalid username or password.")
        except self.cognito_client.exceptions.UserNotConfirmedException:
            self.logger.warning(f"User {username} not confirmed.")
            raise UnauthorizedError("User not confirmed. Please verify your account.")
        except self.cognito_client.exceptions.UserNotFoundException:
            self.logger.warning(f"User {username} not found.")
            raise NotFoundError("User not found.")
        except self.cognito_client.exceptions.TooManyRequestsException:
            self.logger.warning("Too many requests to Cognito (login).")
            raise InternalServerError(
                "Too many login attempts, please try again later."
            )
        except Exception as e:
            self.logger.exception(f"Cognito login error for user {username}: {e}")
            raise InternalServerError(
                "Authentication service error. Please try again later."
            )

    def handle_refresh(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Refreshes authentication tokens using AWS Cognito based on a provided refresh token.
        
        Validates the presence of a refresh token in the request body and initiates the Cognito REFRESH_TOKEN_AUTH flow to obtain new tokens. Raises HTTP exceptions for missing, invalid, or expired tokens, rate limiting, or unexpected errors.
        
        Parameters:
            request_body (Dict[str, Any]): Dictionary containing the "refreshToken" key.
        
        Returns:
            Dict[str, Any]: A dictionary with refreshed authentication tokens and a success message.
        """
        refresh_token = request_body.get("refreshToken")

        if not refresh_token:
            self.logger.warning("Missing refreshToken for token refresh.")
            raise BadRequestError("Refresh token is required.")

        try:
            auth_response = self.cognito_client.initiate_auth(
                AuthFlow="REFRESH_TOKEN_AUTH",
                ClientId=self.config.cognito_client_id,
                AuthParameters={
                    "REFRESH_TOKEN": refresh_token,
                },
            )
            self.logger.info("Successfully refreshed tokens.")

            auth_result = auth_response.get("AuthenticationResult", {})
            return {
                "message": "Token refreshed successfully",
                "idToken": auth_result.get("IdToken"),
                "accessToken": auth_result.get("AccessToken"),
                "expiresIn": auth_result.get("ExpiresIn"),
            }

        except self.cognito_client.exceptions.NotAuthorizedException:
            self.logger.warning("Refresh token is invalid or expired.")
            raise UnauthorizedError(
                "Refresh token invalid or expired. Please re-authenticate."
            )
        except self.cognito_client.exceptions.TooManyRequestsException:
            self.logger.warning("Too many requests to Cognito (refresh).")
            raise InternalServerError(
                "Too many refresh attempts, please try again later."
            )
        except Exception as e:
            self.logger.exception(f"Cognito refresh error: {e}")
            raise InternalServerError(
                "Authentication service error. Please try again later."
            )


_auth_service = None

_lock = threading.Lock()


def get_auth_service() -> AuthService:
    """
    Returns a singleton instance of AuthService, ensuring thread-safe initialisation.

    Initialises the AuthService with a new AuthConfig if it has not already been created, using double-checked locking to guarantee only one instance exists across threads.
    """
    global _auth_service
    if _auth_service is None:
        with _lock:
            if _auth_service is None:
                config = AuthConfig()
                _auth_service = AuthService(config)
    return _auth_service
