from unittest.mock import patch, MagicMock

import pytest

from s3 import get_s3_client


class TestGetS3Client:

    def test_get_s3_client_success(self):
        mock_logger = MagicMock()
        region = "eu-west-2"

        with patch("boto3.client") as mock_boto3_client:
            mock_client = MagicMock()
            mock_boto3_client.return_value = mock_client

            result = get_s3_client(region, mock_logger)

            mock_boto3_client.assert_called_once_with("s3", region_name=region)
            assert result == mock_client
            mock_logger.info.assert_called_once_with(
                "Initialized S3 client with default endpoint"
            )

    def test_get_s3_client_exception(self):
        mock_logger = MagicMock()
        region = "eu-west-2"

        with patch("boto3.client") as mock_boto3_client:
            mock_boto3_client.side_effect = Exception("Connection error")

            with pytest.raises(Exception) as exc_info:
                get_s3_client(region, mock_logger)

            assert "Connection error" in str(exc_info.value)
            mock_logger.error.assert_called_once_with(
                "Failed to initialize S3 client", exc_info=True
            )
