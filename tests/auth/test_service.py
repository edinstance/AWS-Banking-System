import json

from tests.auth.conftest import (
    MockUserNotConfirmedException,
    MockTooManyRequestsException,
    MockNotAuthorizedException,
    MockUserNotFoundException,
)


class TestAuthService:

    def test_no_username_or_password(self, auth_service_instance):
        """
        Tests that login fails with a 400 status code when username or password is missing.

        Verifies that the authentication service returns an appropriate error message if required credentials are not provided in the login request.
        """
        request_body = {}
        result = auth_service_instance.handle_login(request_body)

        assert result["statusCode"] == 400
        result_body = json.loads(result["body"])
        assert result_body["error"] == "Username and password are required."

    def test_handle_login_success(self, auth_service_instance, mock_cognito_user_pool):
        """
        Tests successful login flow, verifying token issuance and logging.

        Creates a user in the mocked Cognito user pool, sets a permanent password, and submits valid credentials to the authentication service. Asserts that the response contains a 200 status code, a success message, authentication tokens, and that a success log entry is recorded.
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

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] == "Login successful!"
        assert "idToken" in body
        assert "accessToken" in body
        assert "refreshToken" in body
        assert "expiresIn" in body
        auth_service_instance.logger.info.assert_called_once_with(
            f"Successfully initiated auth for user: {test_username}"
        )

    def test_handle_login_user_not_confirmed(
        self, auth_service_instance_with_mock_cognito
    ):
        """
        Tests that login returns a 403 status and appropriate error message when the user is not confirmed.

        Simulates a Cognito exception for an unconfirmed user and verifies the response and logging behaviour.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client

        mock_cognito_client.admin_initiate_auth.side_effect = (
            MockUserNotConfirmedException("User is not confirmed.")
        )

        request_body = {"username": "unconfirmed_user", "password": "Password123!"}
        response = auth_service_instance_with_mock_cognito.handle_login(request_body)

        assert response["statusCode"] == 403

        response_body_dict = json.loads(response["body"])
        assert (
            response_body_dict["error"]
            == "User not confirmed. Please verify your account."
        )

        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "User unconfirmed_user not confirmed."
        )
        mock_cognito_client.admin_initiate_auth.assert_called_once()

    def test_handle_login_not_authorized_exception(
        self, auth_service_instance_with_mock_cognito
    ):
        """
        Tests that login with invalid credentials returns a 401 status and appropriate error message.

        Simulates a Cognito not authorized exception during login and verifies that the response contains a 401 status code, an error message about invalid credentials, and that a warning is logged.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.admin_initiate_auth.side_effect = (
            MockNotAuthorizedException("Invalid credentials.")
        )

        request_body = {"username": "test_user", "password": "wrong_password"}
        response = auth_service_instance_with_mock_cognito.handle_login(request_body)

        assert response["statusCode"] == 401
        assert json.loads(response["body"]) == {
            "error": "Invalid username or password."
        }
        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "Authentication failed for user: test_user (Invalid credentials)."
        )
        mock_cognito_client.admin_initiate_auth.assert_called_once()

    def test_handle_login_user_not_found_exception(
        self, auth_service_instance_with_mock_cognito
    ):
        """
        Tests that login returns a 404 status and appropriate error message when the user does not exist.

        Simulates a Cognito user not found exception during login and verifies the response and logging behaviour.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.admin_initiate_auth.side_effect = MockUserNotFoundException(
            "User not found."
        )

        request_body = {"username": "non_existent_user", "password": "any_password"}
        response = auth_service_instance_with_mock_cognito.handle_login(request_body)

        assert response["statusCode"] == 404
        assert json.loads(response["body"]) == {"error": "User not found."}
        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "User non_existent_user not found."
        )
        mock_cognito_client.admin_initiate_auth.assert_called_once()

    def test_handle_login_too_many_requests_exception(
        self, auth_service_instance_with_mock_cognito
    ):
        """
        Tests that the login handler returns a 429 status and appropriate error message when Cognito rate limits login attempts.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.admin_initiate_auth.side_effect = (
            MockTooManyRequestsException("Too many attempts.")
        )

        request_body = {"username": "test_user", "password": "some_password"}
        response = auth_service_instance_with_mock_cognito.handle_login(request_body)

        assert response["statusCode"] == 429
        assert json.loads(response["body"]) == {
            "error": "Too many login attempts, please try again later."
        }
        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "Too many requests to Cognito (login)."
        )
        mock_cognito_client.admin_initiate_auth.assert_called_once()

    def test_handle_login_generic_exception(
        self, auth_service_instance_with_mock_cognito
    ):
        """
        Tests that a generic exception during login results in a 500 response and appropriate error logging.

        Simulates an unexpected error from the Cognito client during authentication and verifies that the service returns a 500 status code, a generic error message in the response body, and logs the exception.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.admin_initiate_auth.side_effect = Exception(
            "Some unexpected error"
        )

        request_body = {"username": "test_user", "password": "password"}
        response = auth_service_instance_with_mock_cognito.handle_login(request_body)

        assert response["statusCode"] == 500
        assert json.loads(response["body"]) == {
            "error": "Authentication service error. Please try again later."
        }
        auth_service_instance_with_mock_cognito.logger.exception.assert_called_once_with(
            "Cognito login error for user test_user: Some unexpected error"
        )
        mock_cognito_client.admin_initiate_auth.assert_called_once()

    def test_handle_refresh_missing_refresh_token(
        self, auth_service_instance_with_mock_cognito
    ):
        """
        Tests that the token refresh handler returns a 400 error when the refresh token is missing.

        Verifies that the response contains an appropriate error message and that a warning is logged.
        """
        request_body = {}
        response = auth_service_instance_with_mock_cognito.handle_refresh(request_body)

        assert response["statusCode"] == 400
        assert json.loads(response["body"]) == {"error": "Refresh token is required."}
        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "Missing refreshToken for token refresh."
        )

    def test_handle_refresh_success(
        self, auth_service_instance_with_mock_cognito, mock_cognito_user_pool
    ):
        """
        Tests successful token refresh using a valid refresh token.

        Verifies that the authentication service returns new tokens and a 200 status code when provided with a valid refresh token, and that the Cognito client and logging are called as expected.
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

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] == "Tokens refreshed successfully!"
        assert body["idToken"] == "new_mock_id_token"
        assert body["accessToken"] == "new_mock_access_token"
        assert body["expiresIn"] == 3600

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
        self, auth_service_instance_with_mock_cognito
    ):
        """
        Tests that handle_refresh returns a 401 status and appropriate error message when an invalid or expired refresh token triggers a NotAuthorizedException.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.initiate_auth.side_effect = MockNotAuthorizedException(
            "Invalid token."
        )

        request_body = {"refreshToken": "invalid_refresh_token"}
        response = auth_service_instance_with_mock_cognito.handle_refresh(request_body)

        assert response["statusCode"] == 401
        assert json.loads(response["body"]) == {
            "error": "Refresh token invalid or expired. Please re-authenticate."
        }
        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "Refresh token is invalid or expired."
        )
        mock_cognito_client.initiate_auth.assert_called_once()

    def test_handle_refresh_too_many_requests_exception(
        self, auth_service_instance_with_mock_cognito
    ):
        """
        Tests that the refresh handler returns a 429 status code and appropriate error message when Cognito raises a rate limiting exception during token refresh.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.initiate_auth.side_effect = MockTooManyRequestsException(
            "Too many refresh attempts."
        )

        request_body = {"refreshToken": "valid_refresh_token"}
        response = auth_service_instance_with_mock_cognito.handle_refresh(request_body)

        assert response["statusCode"] == 429
        assert json.loads(response["body"]) == {
            "error": "Too many refresh attempts, please try again later."
        }
        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "Too many requests to Cognito (refresh)."
        )
        mock_cognito_client.initiate_auth.assert_called_once()

    def test_handle_refresh_generic_exception(
        self, auth_service_instance_with_mock_cognito
    ):
        """
        Tests that a generic exception during token refresh returns a 500 status and logs the error.

        Simulates an unexpected exception from the Cognito client when refreshing tokens, verifying that the authentication service responds with a 500 status code, a generic error message, and logs the exception.
        """
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.initiate_auth.side_effect = Exception(
            "Another unexpected error"
        )

        request_body = {"refreshToken": "valid_refresh_token"}
        response = auth_service_instance_with_mock_cognito.handle_refresh(request_body)

        assert response["statusCode"] == 500
        assert json.loads(response["body"]) == {
            "error": "Authentication service error. Please try again later."
        }
        auth_service_instance_with_mock_cognito.logger.exception.assert_called_once_with(
            "Cognito refresh error: Another unexpected error"
        )
        mock_cognito_client.initiate_auth.assert_called_once()
