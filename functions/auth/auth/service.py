import threading
from typing import Dict, Any

import boto3
from aws_lambda_powertools import Logger

from .config import AuthConfig
from .helpers import create_response


class AuthService:
    def __init__(self, config: AuthConfig, cognito_client=None):
        self.config = config
        self.logger = Logger(service="AuthLambda", level=config.log_level)
        self.cognito_client = cognito_client or boto3.client("cognito-idp")

    def handle_login(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        username = request_body.get("username")
        password = request_body.get("password")

        if not username or not password:
            self.logger.warning("Missing username or password for login.")
            return create_response(
                400, {"error": "Username and password are required."}, "POST"
            )

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
            return create_response(
                200,
                {
                    "message": "Login successful!",
                    "idToken": auth_result.get("IdToken"),
                    "accessToken": auth_result.get("AccessToken"),
                    "refreshToken": auth_result.get("RefreshToken"),
                    "expiresIn": auth_result.get("ExpiresIn"),
                },
                "POST",
            )

        except self.cognito_client.exceptions.NotAuthorizedException:
            self.logger.warning(
                f"Authentication failed for user: {username} (Invalid credentials)."
            )
            return create_response(
                401, {"error": "Invalid username or password."}, "POST"
            )
        except self.cognito_client.exceptions.UserNotConfirmedException:
            self.logger.warning(f"User {username} not confirmed.")
            return create_response(
                403,
                {"error": "User not confirmed. Please verify your account."},
                "POST",
            )
        except self.cognito_client.exceptions.UserNotFoundException:
            self.logger.warning(f"User {username} not found.")
            return create_response(404, {"error": "User not found."}, "POST")
        except self.cognito_client.exceptions.TooManyRequestsException:
            self.logger.warning("Too many requests to Cognito (login).")
            return create_response(
                429,
                {"error": "Too many login attempts, please try again later."},
                "POST",
            )
        except Exception as e:
            self.logger.exception(f"Cognito login error for user {username}: {e}")
            return create_response(
                500,
                {"error": "Authentication service error. Please try again later."},
                "POST",
            )

    def handle_refresh(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """Handles token refresh requests using a refresh token with Cognito."""
        refresh_token = request_body.get("refreshToken")

        if not refresh_token:
            self.logger.warning("Missing refreshToken for token refresh.")
            return create_response(400, {"error": "Refresh token is required."}, "POST")

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
            return create_response(
                200,
                {
                    "message": "Tokens refreshed successfully!",
                    "idToken": auth_result.get("IdToken"),
                    "accessToken": auth_result.get("AccessToken"),
                    "expiresIn": auth_result.get("ExpiresIn"),
                },
                "POST",
            )

        except self.cognito_client.exceptions.NotAuthorizedException:
            self.logger.warning("Refresh token is invalid or expired.")
            return create_response(
                401,
                {"error": "Refresh token invalid or expired. Please re-authenticate."},
                "POST",
            )
        except self.cognito_client.exceptions.TooManyRequestsException:
            self.logger.warning("Too many requests to Cognito (refresh).")
            return create_response(
                429,
                {"error": "Too many refresh attempts, please try again later."},
                "POST",
            )
        except Exception as e:
            self.logger.exception(f"Cognito refresh error: {e}")
            return create_response(
                500,
                {"error": "Authentication service error. Please try again later."},
                "POST",
            )


_auth_service = None

_lock = threading.Lock()


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        with _lock:
            if _auth_service is None:
                config = AuthConfig()
                _auth_service = AuthService(config)
    return _auth_service
