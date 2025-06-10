import json
from unittest.mock import MagicMock, patch

from functions.auth.auth.app import lambda_handler


class TestApp:

    def test_options_request(self):
        context = MagicMock()
        context.aws_request_id = "test-request-id"
        result = lambda_handler({"httpMethod": "OPTIONS"}, context)

        assert result["statusCode"] == 200
        assert result["headers"]

    def test_unsupported_method(self):
        context = MagicMock()
        context.aws_request_id = "test-request-id"

        result = lambda_handler({"httpMethod": "GET"}, context)

        assert result["statusCode"] == 405

        body = json.loads(result["body"])
        assert body.get("error") == "Method Not Allowed"

    def test_invalid_json(self):
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
