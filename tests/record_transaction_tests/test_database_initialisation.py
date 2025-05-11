from unittest.mock import patch, MagicMock

from boto3.resources.base import ServiceResource
from moto import mock_aws

from functions.record_transactions import app
from functions.record_transactions.app import get_dynamodb_resource


def test_table_initialization_with_environment_variable(app_with_mocked_table):
    """Test table initialization when TRANSACTIONS_TABLE_NAME is set."""
    # No need to patch the logger since it's already initialized in the app
    assert app_with_mocked_table.table is not None
    assert app_with_mocked_table.TRANSACTIONS_TABLE_NAME == "test-transactions-table"


def test_table_initialization_without_environment_variable(app_without_table):
    """Test behavior when TRANSACTIONS_TABLE_NAME is not set."""
    # The logger is already initialized, so we need to check if critical was called
    # during the module reload, which is hard to test directly
    assert app_without_table.table is None


def test_lambda_handler_with_uninitialized_table(app_without_table):
    """Test lambda_handler behavior when the table is not initialized."""
    # Create a mock context
    mock_context = MagicMock()
    mock_context.aws_request_id = "test-request-id"
    mock_context.function_name = "test-function"

    # Patch the logger to capture calls
    with patch.object(app_without_table, 'logger') as mock_logger:
        # Make sure the inject_lambda_context decorator works
        mock_logger.inject_lambda_context.return_value = lambda f: f

        # Call the handler
        response = app_without_table.lambda_handler({}, mock_context)

        # Verify the response
        assert response["statusCode"] == 500
        assert "Server configuration error" in response["body"]

        # Verify the logger was called
        mock_logger.error.assert_called_with("DynamoDB table resource is not initialized")


def test_lambda_handler_with_initialized_table(app_with_mocked_table):
    """Test lambda_handler with initialized table but invalid request."""
    # Create a mock context
    mock_context = MagicMock()
    mock_context.aws_request_id = "test-request-id"
    mock_context.function_name = "test-function"

    # Patch the logger to capture calls
    with patch.object(app_with_mocked_table, 'logger') as mock_logger:
        # Make sure the inject_lambda_context decorator works
        mock_logger.inject_lambda_context.return_value = lambda f: f

        # Create an event without an idempotency key
        event = {"headers": {}}

        # Call the handler
        response = app_with_mocked_table.lambda_handler(event, mock_context)

        # Verify the response
        assert response["statusCode"] == 400
        assert "Idempotency-Key header is required" in response["body"]

        # Verify the table is initialized
        assert app_with_mocked_table.table is not None


class TestGetDynamoDBResource:

    def test_default_endpoint(self, aws_credentials, monkeypatch):
        """Test that the function uses the default endpoint when no custom endpoint is set."""
        # Ensure DYNAMODB_ENDPOINT is not set
        monkeypatch.delenv("DYNAMODB_ENDPOINT", raising=False)

        # Mock the logger to verify it's called correctly
        mock_logger = MagicMock()
        with patch('functions.record_transactions.app.logger', mock_logger), mock_aws():
            # Call the function
            resource = get_dynamodb_resource()

            # Verify the resource is a boto3 DynamoDB resource
            assert isinstance(resource, ServiceResource)

            # Verify the logger was called correctly
            mock_logger.debug.assert_called_with("Using default DynamoDB endpoint")

            # Verify we can list tables (basic functionality check)
            tables = list(resource.tables.all())
            assert isinstance(tables, list)

    def test_custom_endpoint(self, monkeypatch):
        """Test that the function uses a custom endpoint when specified in environment variables."""
        # Setup
        custom_endpoint = "http://localhost:8000"

        # Mocks
        mock_boto3 = MagicMock()
        mock_resource = MagicMock()
        mock_logger = MagicMock()
        mock_boto3.resource.return_value = mock_resource

        # Patch dependencies and environment variable directly within the application
        with patch('functions.record_transactions.app.boto3', mock_boto3), \
                patch('functions.record_transactions.app.logger', mock_logger), \
                patch('functions.record_transactions.app.DYNAMODB_ENDPOINT', custom_endpoint):
            result = app.get_dynamodb_resource()

            mock_boto3.resource.assert_called_once_with('dynamodb', endpoint_url=custom_endpoint)
            mock_logger.debug.assert_called_with(f"Using custom DynamoDB endpoint: {custom_endpoint}")
            assert result == mock_resource

    def test_empty_endpoint_string(self, aws_credentials, monkeypatch):
        """Test that the function uses the default endpoint when an empty string is provided."""
        monkeypatch.setenv("DYNAMODB_ENDPOINT", "")

        mock_logger = MagicMock()

        with patch('functions.record_transactions.app.logger', mock_logger), mock_aws():
            # Call the function
            resource = get_dynamodb_resource()

            mock_logger.debug.assert_called_with("Using default DynamoDB endpoint")

            tables = list(resource.tables.all())
            assert isinstance(tables, list)

    def test_integration_with_dynamo_table(self, app_with_mocked_table, dynamo_table):
        """Test that the function works with the mocked DynamoDB table fixture."""

        # Call get_dynamodb_resource directly
        resource = app_with_mocked_table.get_dynamodb_resource()

        # Verify we can access the table
        table = resource.Table(dynamo_table)
        assert table.table_name == dynamo_table

        # Verify the table exists and has the expected structure
        table_description = table.meta.client.describe_table(TableName=dynamo_table)
        assert table_description['Table']['TableName'] == dynamo_table

        # Verify the GSI exists
        gsi = table_description['Table']['GlobalSecondaryIndexes']
        assert len(gsi) == 1
        assert gsi[0]['IndexName'] == 'IdempotencyKeyIndex'
