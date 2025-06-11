import json
from unittest.mock import MagicMock, patch

from functions.auth.auth.app import lambda_handler


class TestApp:

    def test_options_request(self):
        """
        Tests that an OPTIONS HTTP request to the lambda handler returns a 200 status code and includes headers.
        """
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        result = lambda_handler({"httpMethod": "OPTIONS"}, context)

        assert result["statusCode"] == 200
        assert result["headers"]

    def test_no_http_method(self):
        """
        Tests that the lambda_handler returns a 400 status code when the HTTP method is missing from the event.
        """
        context = MagicMock()
        context.aws_request_id = "test-request-id"

        result = lambda_handler({}, context)

        assert result["statusCode"] == 400

    def test_unsupported_method(self):
        """
        Tests that the lambda_handler returns a 405 status code and appropriate error message when an unsupported HTTP method is used.
        """
        context = MagicMock()
        context.aws_request_id = "test-request-id"

        result = lambda_handler({"httpMethod": "GET"}, context)

        assert result["statusCode"] == 405

        body = json.loads(result["body"])
        assert body.get("error") == "Method Not Allowed"

    def test_invalid_json(self):
        """
        Tests that the lambda_handler returns a 400 status code and appropriate error message when the request body contains invalid JSON.
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
        body = json.loads(result["body"])
        assert body.get("error") == "Invalid JSON format in request body"

    def test_invalid_path(self):
        """
        Tests that the lambda_handler returns a 404 status code and appropriate error message when an unsupported path is requested.
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
        assert body.get("error") == "Not Found"

    def test_post_login_route(self):
        """
        Tests that a POST request to the /auth/login route returns a successful login response.

        Mocks the authentication service to simulate a successful login, sends a POST request with valid credentials, and verifies the response status code, message, and that the login handler is called once.
        """
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        with patch("functions.auth.auth.app.get_auth_service") as mock_get_auth_service:
            mock_auth_service = MagicMock()
            mock_get_auth_service.return_value = mock_auth_service
            mock_auth_service.handle_login.return_value = {
                "statusCode": 200,
                "body": json.dumps({"message": "Login successful"}),
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

    def test_post_refresh_route(self):
        """
        Tests that a POST request to the /auth/refresh route returns a successful token refresh response.

        Mocks the authentication service to simulate a successful token refresh, sends a POST request with a refresh token, and asserts that the response status code is 200, the response body contains the expected message, and the refresh handler is called exactly once.
        """
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        with patch("functions.auth.auth.app.get_auth_service") as mock_get_auth_service:
            mock_auth_service = MagicMock()
            mock_get_auth_service.return_value = mock_auth_service
            mock_auth_service.handle_refresh.return_value = {
                "statusCode": 200,
                "body": json.dumps({"message": "Token refreshed"}),
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
