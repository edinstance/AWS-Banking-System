from unittest.mock import patch, MagicMock

import pytest

from sfn import get_sfn_client


class TestGetSfnClient:

    def test_get_sfn_client_success(self):
        mock_logger = MagicMock()
        region = "eu-west-2"

        with patch("boto3.client") as mock_boto3_client:
            mock_client = MagicMock()
            mock_boto3_client.return_value = mock_client

            result = get_sfn_client(region, mock_logger)

            mock_boto3_client.assert_called_once_with(
                "stepfunctions", region_name=region
            )
            assert result == mock_client
            mock_logger.info.assert_called_once_with("Initialized SFN client with default endpoint")

    def test_get_sfn_client_exception(self):
        mock_logger = MagicMock()
        region = "eu-west-2"

        with patch("boto3.client") as mock_boto3_client:
            mock_boto3_client.side_effect = Exception("Connection error")

            with pytest.raises(Exception) as exc_info:
                get_sfn_client(region, mock_logger)

            assert "Connection error" in str(exc_info.value)
            mock_logger.error.assert_called_once_with(
                "Failed to initialize SFN client", exc_info=True
            )
