import json
from unittest.mock import MagicMock, patch


from functions.auth.auth.app import lambda_handler


class TestApp:

    def test_options_request(self, auth_service_instance_with_mock_cognito):
        """
        Test that an HTTP OPTIONS request to the lambda handler for the /auth/login path returns a 204 status code.
        """
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        result = lambda_handler(
            {"httpMethod": "OPTIONS", "path": "/auth/login"}, context
        )

        assert result["statusCode"] == 204

    def test_invalid_json(self, auth_service_instance_with_mock_cognito):
        """
        Test that the lambda_handler returns a 400 status code and an error message when given a malformed JSON body in a POST request to /auth/login.
        """
        context = MagicMock()
        context.aws_request_id = "test-request-id"

        result = lambda_handler(
            {
                "httpMethod": "POST",
                "path": "/auth/login",
                "body": "{invalid json",
            },
            context,
        )
        assert result["statusCode"] == 400
        assert result["body"] == "Invalid JSON format in request body."

    def test_invalid_path(self, auth_service_instance_with_mock_cognito):
        """
        Test that the lambda_handler returns a 404 status code and a 'Not found' message for unsupported request paths.
        """
        context = MagicMock()
        context.aws_request_id = "test-request-id"

        result = lambda_handler(
            {
                "httpMethod": "POST",
                "path": "/fake",
            },
            context,
        )

        assert result["statusCode"] == 404
        body = json.loads(result["body"])
        assert body.get("message") == "Not found"

    def test_post_login_route(self, auth_service_instance_with_mock_cognito):
        """
        Test that a POST request to the /auth/login route returns a successful login response.

        Simulates a successful login by mocking the authentication service, sends a POST request with valid credentials, and verifies the response status code, response message, and that the login handler is called exactly once.
        """
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        with patch("functions.auth.auth.app.get_auth_service") as mock_get_auth_service:
            mock_auth_service = MagicMock()
            mock_get_auth_service.return_value = mock_auth_service
            mock_auth_service.handle_login.return_value = {
                "message": "Login successful"
            }
            result = lambda_handler(
                {
                    "httpMethod": "POST",
                    "path": "/auth/login",
                    "body": json.dumps({"username": "test", "password": "password"}),
                },
                context,
            )

            assert result["statusCode"] == 200
            body = json.loads(result["body"])
            assert body.get("message") == "Login successful"
            mock_auth_service.handle_login.assert_called_once()

    def test_post_refresh_route(self, auth_service_instance_with_mock_cognito):
        """
        Test that a POST request to the /auth/refresh route returns a successful token refresh response.

        Simulates a successful token refresh by mocking the authentication service, sends a POST request with a refresh token, and verifies that the response status code is 200, the response body contains the expected message, and the refresh handler is called once.
        """
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        with patch("functions.auth.auth.app.get_auth_service") as mock_get_auth_service:
            mock_auth_service = MagicMock()
            mock_get_auth_service.return_value = mock_auth_service
            mock_auth_service.handle_refresh.return_value = {
                "message": "Token refreshed"
            }
            result = lambda_handler(
                {
                    "httpMethod": "POST",
                    "path": "/auth/refresh",
                    "body": json.dumps({"refreshToken": "some_refresh_token"}),
                },
                context,
            )

            assert result["statusCode"] == 200
            body = json.loads(result["body"])
            assert body.get("message") == "Token refreshed"
            mock_auth_service.handle_refresh.assert_called_once()
