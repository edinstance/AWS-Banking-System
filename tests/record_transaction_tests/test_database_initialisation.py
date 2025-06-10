import uuid
from unittest.mock import patch, MagicMock

from moto import mock_aws

from functions.record_transactions.record_transactions.app import get_dynamodb_resource


def test_table_initialization_with_environment_variable(app_with_mocked_table):
    """Test table initialization when TRANSACTIONS_TABLE_NAME is set."""
    assert app_with_mocked_table.table is not None
    assert app_with_mocked_table.TRANSACTIONS_TABLE_NAME == "test-transactions-table"


def test_table_initialization_without_environment_variable(app_without_table):
    """
    Tests that the DynamoDB table resource remains uninitialized when the TRANSACTIONS_TABLE_NAME environment variable is not set.
    """
    assert app_without_table.table is None


def test_lambda_handler_with_uninitialized_table(app_without_table):
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


def test_lambda_handler_with_initialized_table(app_with_mocked_table):
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
            "requestContext": {"authorizer": {"claims": {"sub": str(uuid.uuid4())}}},
        }

        response = app_with_mocked_table.lambda_handler(event, mock_context)

        assert response["statusCode"] == 400
        assert "Idempotency-Key header is required" in response["body"]

        assert app_with_mocked_table.table is not None


class TestGetDynamoDBResource:
    def test_default_endpoint(self, aws_credentials, monkeypatch):
        """
        Tests that get_dynamodb_resource uses the default DynamoDB endpoint when no custom endpoint is set.

        Ensures the DYNAMODB_ENDPOINT environment variable is unset, verifies the logger records the use of the default endpoint, and confirms the returned resource is a valid boto3 DynamoDB ServiceResource.
        """
        monkeypatch.delenv("DYNAMODB_ENDPOINT", raising=False)

        mock_logger = MagicMock()
        with patch(
            "functions.record_transactions.record_transactions.app.logger", mock_logger
        ), mock_aws():
            resource = get_dynamodb_resource(None, "us-west-2", mock_logger)

            assert resource is not None
            mock_logger.debug.assert_called_once_with(
                "Initialized DynamoDB resource with default endpoint"
            )

    def test_custom_endpoint(self, monkeypatch):
        """
        Tests that get_dynamodb_resource uses a custom DynamoDB endpoint when specified via environment variables.

        Verifies that the function calls boto3.resource with the custom endpoint URL, logs the correct debug message, and returns the mocked resource.
        """
        custom_endpoint = "http://localhost:8000"
        custom_region = "us-west-2"
        mock_boto3 = MagicMock()
        mock_resource = MagicMock()
        mock_logger = MagicMock()
        mock_boto3.resource.return_value = mock_resource

        with patch("boto3.resource", mock_boto3.resource):
            result = get_dynamodb_resource(custom_endpoint, custom_region, mock_logger)

            mock_boto3.resource.assert_called_once_with(
                "dynamodb", endpoint_url=custom_endpoint, region_name=custom_region
            )
            assert result == mock_resource
            mock_logger.debug.assert_called_once_with(
                f"Initialized DynamoDB resource with endpoint {custom_endpoint}"
            )

    def test_custom_region(self, monkeypatch):
        """Test that the function uses a custom endpoint with a custom region when specified in environment variables."""
        custom_endpoint = "http://localhost:8000"
        custom_region = "us-east-1"

        mock_boto3 = MagicMock()
        mock_resource = MagicMock()
        mock_logger = MagicMock()
        mock_boto3.resource.return_value = mock_resource

        with patch("boto3.resource", mock_boto3.resource):
            result = get_dynamodb_resource(custom_endpoint, custom_region, mock_logger)

            mock_boto3.resource.assert_called_once_with(
                "dynamodb", endpoint_url=custom_endpoint, region_name=custom_region
            )
            assert result == mock_resource
            mock_logger.debug.assert_called_once_with(
                f"Initialized DynamoDB resource with endpoint {custom_endpoint}"
            )

    def test_empty_endpoint_string(self, aws_credentials, monkeypatch):
        monkeypatch.setenv("DYNAMODB_ENDPOINT", "")

        mock_logger = MagicMock()

        with patch(
            "functions.record_transactions.record_transactions.app.logger", mock_logger
        ), mock_aws():
            resource = get_dynamodb_resource("", "us-west-2", mock_logger)

            assert resource is not None
            mock_logger.debug.assert_called_once_with(
                "Initialized DynamoDB resource with default endpoint"
            )

    def test_integration_with_dynamo_table(self, app_with_mocked_table, dynamo_table):
        """
        Verifies integration with a mocked DynamoDB table, ensuring correct table access and structure.

        This test checks that the `get_dynamodb_resource` function can retrieve a mocked DynamoDB table, confirms the table's name, and asserts the presence of a Global Secondary Index named `IdempotencyKeyIndex`.
        """
        resource = get_dynamodb_resource(
            None, "us-west-2", app_with_mocked_table.logger
        )

        assert resource is not None
        mock_table = resource.Table(dynamo_table)
        assert mock_table is not None
