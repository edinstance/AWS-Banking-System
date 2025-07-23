import pytest
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    UnauthorizedError,
    NotFoundError,
    InternalServerError,
)

from functions.auth.auth.config import AuthConfig
from authentication.exceptions import AuthConfigurationError
from functions.auth.auth.service import AuthService

from tests.functions.auth.conftest import (
    MockUserNotConfirmedException,
    MockTooManyRequestsException,
    MockNotAuthorizedException,
    MockUserNotFoundException,
)


class TestAuthService:

    def test_service_init_exception(self, mock_cognito_user_pool):
        config = AuthConfig()
        with pytest.raises(AuthConfigurationError):
            service = AuthService(
                config=config, cognito_client=mock_cognito_user_pool["cognito_client"]
            )

            assert service is None

    def test_no_username_or_password(self, auth_service_instance):
        """
        Test that login raises BadRequestError when username or password is missing.

        Verifies that the authentication service rejects login attempts without required credentials and returns the expected error message.
        """
        request_body = {}
        with pytest.raises(BadRequestError) as exception_info:
            auth_service_instance.handle_login(request_body)

        assert exception_info.type == BadRequestError
        assert exception_info.value.msg == "Username and password are required."

    def test_handle_login_success(
        self, auth_service_instance, mock_cognito_user_pool, cognito_client
    ):
        """
        Test that a user can successfully log in and receive authentication tokens.

        Creates a user in a mocked Cognito user pool, sets a permanent password, and submits valid credentials to the authentication service. Asserts that the response includes authentication tokens, a success message, and that a success log entry is recorded.
        """
        test_username = "test_user@example.com"
        test_password = "Password123!"

        cognito_client = auth_service_instance.cognito_client

        cognito_client.admin_create_user(
            UserPoolId=mock_cognito_user_pool["user_pool_id"],
            Username=test_username,
            UserAttributes=[
                {"Name": "email", "Value": test_username},
            ],
        )
        cognito_client.admin_set_user_password(
            UserPoolId=mock_cognito_user_pool["user_pool_id"],
            Username=test_username,
            Password=test_password,
            Permanent=True,
        )

        request_body = {"username": test_username, "password": test_password}
        response = auth_service_instance.handle_login(request_body)

        assert response["message"] == "Login successful!"
        assert "idToken" in response
        assert "accessToken" in response
        assert "refreshToken" in response
        assert "expiresIn" in response
        auth_service_instance.logger.info.assert_called_once_with(
            f"Successfully initiated auth for user: {test_username}"
        )

    def test_handle_login_user_not_confirmed(
        self, auth_service_instance_with_mock_cognito, cognito_client
    ):
        """
        Verify that attempting to log in with an unconfirmed user raises an `UnauthorizedError` with a 403 status and the correct error message.

        Simulates a Cognito exception for an unconfirmed user and asserts that the authentication service raises the expected exception and logs a warning.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client

        mock_cognito_client.admin_initiate_auth.side_effect = (
            MockUserNotConfirmedException("User is not confirmed.")
        )

        request_body = {"username": "unconfirmed_user", "password": "Password123!"}

        with pytest.raises(UnauthorizedError) as exception_info:
            auth_service_instance_with_mock_cognito.handle_login(request_body)

        assert exception_info.type == UnauthorizedError
        assert (
            exception_info.value.msg
            == "User not confirmed. Please verify your account."
        )

        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "User unconfirmed_user not confirmed."
        )
        mock_cognito_client.admin_initiate_auth.assert_called_once()

    def test_handle_login_not_authorized_exception(
        self, auth_service_instance_with_mock_cognito, cognito_client
    ):
        """
        Verify that attempting to log in with invalid credentials raises an UnauthorizedError with a 401 status and logs a warning.

        Simulates a Cognito not authorized exception during login and asserts that the authentication service raises an UnauthorizedError with the expected message and that a warning is logged for the failed authentication attempt.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.admin_initiate_auth.side_effect = (
            MockNotAuthorizedException("Invalid credentials.")
        )

        request_body = {"username": "test_user", "password": "wrong_password"}

        with pytest.raises(UnauthorizedError) as exception_info:
            auth_service_instance_with_mock_cognito.handle_login(request_body)

        assert exception_info.type == UnauthorizedError
        assert exception_info.value.msg == "Invalid username or password."

        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "Authentication failed for user: test_user (Invalid credentials)."
        )
        mock_cognito_client.admin_initiate_auth.assert_called_once()

    def test_handle_login_user_not_found_exception(
        self, auth_service_instance_with_mock_cognito, cognito_client
    ):
        """
        Test that login raises a NotFoundError with a 404 status when the user does not exist.

        Simulates a Cognito user not found exception during login and verifies that the correct exception is raised with the expected message, and that a warning is logged.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.admin_initiate_auth.side_effect = MockUserNotFoundException(
            "User not found."
        )

        request_body = {"username": "non_existent_user", "password": "any_password"}

        with pytest.raises(NotFoundError) as exception_info:
            auth_service_instance_with_mock_cognito.handle_login(request_body)

        assert exception_info.type == NotFoundError
        assert exception_info.value.msg == "User not found."

        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "User non_existent_user not found."
        )
        mock_cognito_client.admin_initiate_auth.assert_called_once()

    def test_handle_login_too_many_requests_exception(
        self, auth_service_instance_with_mock_cognito, cognito_client
    ):
        """
        Verify that the login handler raises an InternalServerError with a 429-style message when Cognito rate limits login attempts.

        Simulates a Cognito rate limiting exception during login and asserts that the correct error message is raised and a warning is logged.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.admin_initiate_auth.side_effect = (
            MockTooManyRequestsException("Too many attempts.")
        )

        request_body = {"username": "test_user", "password": "some_password"}

        with pytest.raises(InternalServerError) as exception_info:
            auth_service_instance_with_mock_cognito.handle_login(request_body)

        assert exception_info.type == InternalServerError
        assert (
            exception_info.value.msg
            == "Too many login attempts, please try again later."
        )

        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "Too many requests to Cognito (login)."
        )
        mock_cognito_client.admin_initiate_auth.assert_called_once()

    def test_handle_login_generic_exception(
        self, auth_service_instance_with_mock_cognito, cognito_client
    ):
        """
        Verify that an unexpected exception during login raises an InternalServerError with a generic error message and logs the exception.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.admin_initiate_auth.side_effect = Exception(
            "Some unexpected error"
        )

        request_body = {"username": "test_user", "password": "password"}

        with pytest.raises(InternalServerError) as exception_info:
            auth_service_instance_with_mock_cognito.handle_login(request_body)

        assert exception_info.type == InternalServerError
        assert (
            exception_info.value.msg
            == "Authentication service error. Please try again later."
        )

        auth_service_instance_with_mock_cognito.logger.exception.assert_called_once_with(
            "Cognito login error for user test_user: Some unexpected error"
        )
        mock_cognito_client.admin_initiate_auth.assert_called_once()

    def test_handle_refresh_missing_refresh_token(
        self, auth_service_instance_with_mock_cognito
    ):
        """
        Test that the token refresh handler raises a BadRequestError when the refresh token is missing.

        Verifies that the exception message indicates the refresh token is required and that a warning is logged.
        """
        request_body = {}

        with pytest.raises(BadRequestError) as exception_info:
            auth_service_instance_with_mock_cognito.handle_refresh(request_body)

        assert exception_info.type == BadRequestError
        assert exception_info.value.msg == "Refresh token is required."

        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "Missing refreshToken for token refresh."
        )

    def test_handle_refresh_success(
        self,
        auth_service_instance_with_mock_cognito,
        mock_cognito_user_pool,
        cognito_client,
    ):
        """
        Test that a valid refresh token results in successful token refresh and correct response data.

        Verifies that the authentication service returns new tokens and a success message when provided with a valid refresh token, and that the Cognito client and logger are called as expected.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.initiate_auth.return_value = {
            "AuthenticationResult": {
                "IdToken": "new_mock_id_token",
                "AccessToken": "new_mock_access_token",
                "ExpiresIn": 3600,
            }
        }

        request_body = {"refreshToken": "valid_refresh_token"}
        response = auth_service_instance_with_mock_cognito.handle_refresh(request_body)

        assert response["message"] == "Token refreshed successfully"
        assert response["idToken"] == "new_mock_id_token"
        assert response["accessToken"] == "new_mock_access_token"
        assert response["expiresIn"] == 3600

        mock_cognito_client.initiate_auth.assert_called_once_with(
            AuthFlow="REFRESH_TOKEN_AUTH",
            ClientId=mock_cognito_user_pool.get("client_id"),
            AuthParameters={
                "REFRESH_TOKEN": "valid_refresh_token",
            },
        )
        auth_service_instance_with_mock_cognito.logger.info.assert_called_once_with(
            "Successfully refreshed tokens."
        )

    def test_handle_refresh_not_authorized_exception(
        self, auth_service_instance_with_mock_cognito, cognito_client
    ):
        """
        Verify that handle_refresh raises an UnauthorizedError with a 401 status and correct message when an invalid or expired refresh token causes a Cognito NotAuthorizedException.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.initiate_auth.side_effect = MockNotAuthorizedException(
            "Invalid token."
        )

        request_body = {"refreshToken": "invalid_refresh_token"}

        with pytest.raises(UnauthorizedError) as exception_info:
            auth_service_instance_with_mock_cognito.handle_refresh(request_body)

        assert exception_info.type == UnauthorizedError
        assert (
            exception_info.value.msg
            == "Refresh token invalid or expired. Please re-authenticate."
        )

        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "Refresh token is invalid or expired."
        )
        mock_cognito_client.initiate_auth.assert_called_once()

    def test_handle_refresh_too_many_requests_exception(
        self, auth_service_instance_with_mock_cognito, cognito_client
    ):
        """
        Verify that the token refresh handler raises an InternalServerError with an appropriate message when Cognito rate limiting occurs during token refresh.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.initiate_auth.side_effect = MockTooManyRequestsException(
            "Too many refresh attempts."
        )

        request_body = {"refreshToken": "valid_refresh_token"}

        with pytest.raises(InternalServerError) as exception_info:
            auth_service_instance_with_mock_cognito.handle_refresh(request_body)

        assert exception_info.type == InternalServerError
        assert (
            exception_info.value.msg
            == "Too many refresh attempts, please try again later."
        )

        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "Too many requests to Cognito (refresh)."
        )
        mock_cognito_client.initiate_auth.assert_called_once()

    def test_handle_refresh_generic_exception(
        self, auth_service_instance_with_mock_cognito, cognito_client
    ):
        """
        Test that a generic exception during token refresh raises an InternalServerError and logs the exception.

        Simulates an unexpected error from the Cognito client when refreshing tokens, verifying that the authentication service raises an InternalServerError with a generic message and logs the exception.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.initiate_auth.side_effect = Exception(
            "Another unexpected error"
        )

        request_body = {"refreshToken": "valid_refresh_token"}

        with pytest.raises(InternalServerError) as exception_info:
            auth_service_instance_with_mock_cognito.handle_refresh(request_body)

        assert exception_info.type == InternalServerError
        assert (
            exception_info.value.msg
            == "Authentication service error. Please try again later."
        )

        auth_service_instance_with_mock_cognito.logger.exception.assert_called_once_with(
            "Cognito refresh error: Another unexpected error"
        )
        mock_cognito_client.initiate_auth.assert_called_once()
