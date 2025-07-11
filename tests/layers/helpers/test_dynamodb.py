from unittest.mock import patch, MagicMock

import pytest

from dynamodb import get_dynamodb_resource


class TestGetDynamoDBResource:
    def test_get_dynamodb_resource_with_endpoint(self):
        """
        Tests that get_dynamodb_resource initialises a DynamoDB resource with a specified endpoint URL and logs the correct debug message.
        """
        mock_logger = MagicMock()
        endpoint_url = "http://localhost:8000"
        region = "eu-west-2"

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
        """
        Tests that get_dynamodb_resource initialises a DynamoDB resource using the default endpoint when no endpoint URL is provided.

        Verifies that the resource is created with the specified region, the returned object matches the mock, and a debug log about using the default endpoint is emitted.
        """
        mock_logger = MagicMock()
        region = "us-west-2"

        with patch("boto3.resource") as mock_boto3_resource:
            mock_resource = MagicMock()
            mock_boto3_resource.return_value = mock_resource

            result = get_dynamodb_resource("", region, mock_logger)

            mock_boto3_resource.assert_called_once_with("dynamodb", region_name=region)
            assert result == mock_resource
            mock_logger.debug.assert_called_once_with(
                "Initialized DynamoDB resource with default endpoint"
            )

    def test_get_dynamodb_resource_error_handling(self):
        """
        Tests that get_dynamodb_resource logs an error and raises an exception when boto3.resource fails.
        """
        mock_logger = MagicMock()
        region = "us-west-2"

        with patch("boto3.resource") as mock_boto3_resource:
            mock_boto3_resource.side_effect = Exception("Connection error")

            with pytest.raises(Exception) as exc_info:
                get_dynamodb_resource("", region, mock_logger)

            assert "Connection error" in str(exc_info.value)
            mock_logger.error.assert_called_once_with(
                "Failed to initialize DynamoDB resource", exc_info=True
            )
