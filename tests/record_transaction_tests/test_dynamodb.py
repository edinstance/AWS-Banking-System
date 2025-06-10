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
