import json

from tests.auth.conftest import MockUserNotConfirmedException, MockTooManyRequestsException, MockNotAuthorizedException, \
    MockUserNotFoundException


class TestAuthService:

    def test_no_username_or_password(self, auth_service_instance):
        request_body = {}
        result = auth_service_instance.handle_login(request_body)

        assert result["statusCode"] == 400
        result_body = json.loads(result["body"])
        assert result_body["error"] == "Username and password are required."

    def test_handle_login_success(self, auth_service_instance, mock_cognito_user_pool):
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

    def test_handle_login_user_not_confirmed(self, auth_service_instance_with_mock_cognito):
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client

        mock_cognito_client.admin_initiate_auth.side_effect = MockUserNotConfirmedException("User is not confirmed.")

        request_body = {"username": "unconfirmed_user", "password": "Password123!"}
        response = auth_service_instance_with_mock_cognito.handle_login(request_body)

        assert response["statusCode"] == 403

        response_body_dict = json.loads(response["body"])
        assert response_body_dict["error"] == "User not confirmed. Please verify your account."

        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "User unconfirmed_user not confirmed."
        )
        mock_cognito_client.admin_initiate_auth.assert_called_once()

    def test_handle_login_not_authorized_exception(self, auth_service_instance_with_mock_cognito):
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.admin_initiate_auth.side_effect = MockNotAuthorizedException("Invalid credentials.")

        request_body = {"username": "test_user", "password": "wrong_password"}
        response = auth_service_instance_with_mock_cognito.handle_login(request_body)

        assert response["statusCode"] == 401
        assert json.loads(response["body"]) == {"error": "Invalid username or password."}
        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "Authentication failed for user: test_user (Invalid credentials)."
        )
        mock_cognito_client.admin_initiate_auth.assert_called_once()

    def test_handle_login_user_not_found_exception(self, auth_service_instance_with_mock_cognito):
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.admin_initiate_auth.side_effect = MockUserNotFoundException("User not found.")

        request_body = {"username": "non_existent_user", "password": "any_password"}
        response = auth_service_instance_with_mock_cognito.handle_login(request_body)

        assert response["statusCode"] == 404
        assert json.loads(response["body"]) == {"error": "User not found."}
        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "User non_existent_user not found."
        )
        mock_cognito_client.admin_initiate_auth.assert_called_once()

    def test_handle_login_too_many_requests_exception(self, auth_service_instance_with_mock_cognito):
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.admin_initiate_auth.side_effect = MockTooManyRequestsException("Too many attempts.")

        request_body = {"username": "test_user", "password": "some_password"}
        response = auth_service_instance_with_mock_cognito.handle_login(request_body)

        assert response["statusCode"] == 429
        assert json.loads(response["body"]) == {"error": "Too many login attempts, please try again later."}
        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "Too many requests to Cognito (login)."
        )
        mock_cognito_client.admin_initiate_auth.assert_called_once()

    def test_handle_login_generic_exception(self, auth_service_instance_with_mock_cognito):
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.admin_initiate_auth.side_effect = Exception("Some unexpected error")

        request_body = {"username": "test_user", "password": "password"}
        response = auth_service_instance_with_mock_cognito.handle_login(request_body)

        assert response["statusCode"] == 500
        assert json.loads(response["body"]) == {"error": "Authentication service error. Please try again later."}
        auth_service_instance_with_mock_cognito.logger.exception.assert_called_once_with(
            "Cognito login error for user test_user: Some unexpected error"
        )
        mock_cognito_client.admin_initiate_auth.assert_called_once()

    def test_handle_refresh_missing_refresh_token(self, auth_service_instance_with_mock_cognito):
        request_body = {}
        response = auth_service_instance_with_mock_cognito.handle_refresh(request_body)

        assert response["statusCode"] == 400
        assert json.loads(response["body"]) == {"error": "Refresh token is required."}
        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "Missing refreshToken for token refresh."
        )

    def test_handle_refresh_success(self, auth_service_instance_with_mock_cognito, mock_cognito_user_pool):
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

    def test_handle_refresh_not_authorized_exception(self, auth_service_instance_with_mock_cognito):
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.initiate_auth.side_effect = MockNotAuthorizedException("Invalid token.")

        request_body = {"refreshToken": "invalid_refresh_token"}
        response = auth_service_instance_with_mock_cognito.handle_refresh(request_body)

        assert response["statusCode"] == 401
        assert json.loads(response["body"]) == {"error": "Refresh token invalid or expired. Please re-authenticate."}
        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "Refresh token is invalid or expired."
        )
        mock_cognito_client.initiate_auth.assert_called_once()

    def test_handle_refresh_too_many_requests_exception(self, auth_service_instance_with_mock_cognito):
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.initiate_auth.side_effect = MockTooManyRequestsException("Too many refresh attempts.")

        request_body = {"refreshToken": "valid_refresh_token"}
        response = auth_service_instance_with_mock_cognito.handle_refresh(request_body)

        assert response["statusCode"] == 429
        assert json.loads(response["body"]) == {"error": "Too many refresh attempts, please try again later."}
        auth_service_instance_with_mock_cognito.logger.warning.assert_called_once_with(
            "Too many requests to Cognito (refresh)."
        )
        mock_cognito_client.initiate_auth.assert_called_once()

    def test_handle_refresh_generic_exception(self, auth_service_instance_with_mock_cognito):
        mock_cognito_client = auth_service_instance_with_mock_cognito.cognito_client
        mock_cognito_client.initiate_auth.side_effect = Exception("Another unexpected error")

        request_body = {"refreshToken": "valid_refresh_token"}
        response = auth_service_instance_with_mock_cognito.handle_refresh(request_body)

        assert response["statusCode"] == 500
        assert json.loads(response["body"]) == {"error": "Authentication service error. Please try again later."}
        auth_service_instance_with_mock_cognito.logger.exception.assert_called_once_with(
            "Cognito refresh error: Another unexpected error"
        )
        mock_cognito_client.initiate_auth.assert_called_once()