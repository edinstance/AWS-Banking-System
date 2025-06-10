import uuid
from unittest.mock import patch, MagicMock

import pytest

from functions.record_transactions.record_transactions.dynamodb import (
    get_dynamodb_resource,
)


class TestGetDynamoDBResource:
    def test_get_dynamodb_resource_with_endpoint(self):
        mock_logger = MagicMock()
        endpoint_url = "http://localhost:8000"
        region = "us-west-2"

        with patch("boto3.resource") as mock_boto3_resource:
            mock_resource = MagicMock()
            mock_boto3_resource.return_value = mock_resource

            result = get_dynamodb_resource(endpoint_url, region, mock_logger)

            mock_boto3_resource.assert_called_once_with(
                "dynamodb", endpoint_url=endpoint_url, region_name=region
            )
            assert result == mock_resource
            mock_logger.debug.assert_called_once_with(
                f"Initialized DynamoDB resource with endpoint {endpoint_url}"
            )

    def test_get_dynamodb_resource_without_endpoint(self):
        mock_logger = MagicMock()
        region = "us-west-2"

        with patch("boto3.resource") as mock_boto3_resource:
            mock_resource = MagicMock()
            mock_boto3_resource.return_value = mock_resource

            result = get_dynamodb_resource(None, region, mock_logger)

            mock_boto3_resource.assert_called_once_with("dynamodb", region_name=region)
            assert result == mock_resource
            mock_logger.debug.assert_called_once_with(
                "Initialized DynamoDB resource with default endpoint"
            )

    def test_get_dynamodb_resource_error_handling(self):
        mock_logger = MagicMock()
        region = "us-west-2"

        with patch("boto3.resource") as mock_boto3_resource:
            mock_boto3_resource.side_effect = Exception("Connection error")

            with pytest.raises(Exception) as exc_info:
                get_dynamodb_resource(None, region, mock_logger)

            assert "Connection error" in str(exc_info.value)
            mock_logger.error.assert_called_once_with(
                "Failed to initialize DynamoDB resource", exc_info=True
            )

    import uuid
    from unittest.mock import patch, MagicMock

    def test_table_initialization_with_environment_variable(
        self, app_with_mocked_table
    ):
        """Test table initialization when TRANSACTIONS_TABLE_NAME is set."""
        assert app_with_mocked_table.table is not None
        assert (
            app_with_mocked_table.TRANSACTIONS_TABLE_NAME == "test-transactions-table"
        )

    def test_lambda_handler_with_uninitialized_table(self, app_without_table):
        """
        Tests that the lambda handler returns a 500 error and logs an appropriate message when the DynamoDB table resource is uninitialized.

        Verifies that the response contains a server configuration error and that an error log is emitted about the missing table resource.
        """
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"
        mock_context.function_name = "test-function"

        with patch.object(app_without_table, "logger") as mock_logger:
            mock_logger.inject_lambda_context.return_value = lambda f: f

            response = app_without_table.lambda_handler({}, mock_context)

            assert response["statusCode"] == 500
            assert "Server configuration error" in response["body"]

            mock_logger.error.assert_called_with(
                "DynamoDB table resource is not initialized"
            )

    #

    def test_lambda_handler_with_initialized_table(self, app_with_mocked_table):
        """
        Tests the lambda handler's response when the DynamoDB table is initialized but the request lacks the required Idempotency-Key header.

        Asserts that the handler returns a 400 status code with an appropriate error message and confirms the table resource is initialized.
        """
        mock_context = MagicMock()
        mock_context.aws_request_id = "test-request-id"
        mock_context.function_name = "test-function"

        with patch.object(app_with_mocked_table, "logger") as mock_logger:
            mock_logger.inject_lambda_context.return_value = lambda f: f

            event = {
                "headers": {},
                "requestContext": {
                    "authorizer": {"claims": {"sub": str(uuid.uuid4())}}
                },
            }

            response = app_with_mocked_table.lambda_handler(event, mock_context)

            assert response["statusCode"] == 400
            assert "Idempotency-Key header is required" in response["body"]

            assert app_with_mocked_table.table is not None
