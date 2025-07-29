from unittest.mock import patch, MagicMock

import pytest

from sqs import get_sqs_client, send_message_to_sqs


class TestGetSqsClient:
    def test_get_sqs_client_with_endpoint(self):
        mock_logger = MagicMock()
        endpoint_url = "http://localhost:8000"
        region = "eu-west-2"

        with patch("boto3.client") as mock_boto3_client:
            mock_client = MagicMock()
            mock_boto3_client.return_value = mock_client

            result = get_sqs_client(endpoint_url, region, mock_logger)

            mock_boto3_client.assert_called_once_with(
                "sqs", endpoint_url=endpoint_url, region_name=region
            )
            assert result == mock_client
            mock_logger.debug.assert_called_once_with(
                f"Initialized SQS client with endpoint {endpoint_url}"
            )

    def test_get_sqs_client_without_endpoint(self):
        mock_logger = MagicMock()
        region = "eu-west-2"

        with patch("boto3.client") as mock_boto3_client:
            mock_client = MagicMock()
            mock_boto3_client.return_value = mock_client

            result = get_sqs_client("", region, mock_logger)

            mock_boto3_client.assert_called_once_with("sqs", region_name=region)
            assert result == mock_client
            mock_logger.debug.assert_called_once_with(
                "Initialized SQS client with default endpoint"
            )

    def test_get_sqs_client_error_handling(self):
        mock_logger = MagicMock()
        region = "eu-west-2"

        with patch("boto3.client") as mock_boto3_client:
            mock_boto3_client.side_effect = Exception("Connection error")

            with pytest.raises(Exception) as exc_info:
                get_sqs_client("", region, mock_logger)

            assert "Connection error" in str(exc_info.value)
            mock_logger.error.assert_called_once_with(
                "Failed to initialize SQS client", exc_info=True
            )


class TestSendDynamoDbRecordToSQS:
    def test_no_sqs_url(self, mock_sqs_client):
        mock_logger = MagicMock()
        result = send_message_to_sqs(
            message={},
            message_attributes={},
            sqs_endpoint="",
            sqs_url="",
            aws_region="",
            logger=mock_logger,
        )

        assert result is False

    def test_no_sqs_message(self, mock_sqs_client):
        mock_logger = MagicMock()
        result = send_message_to_sqs(
            message={},
            message_attributes={},
            sqs_endpoint="",
            sqs_url="http://localhost:4566/queue/test-queue",
            aws_region="",
            logger=mock_logger,
        )

        assert result is False

    def test_send_message_success(self):
        mock_logger = MagicMock()
        mock_sqs_client = MagicMock()

        record = {
            "dynamodb": {
                "ApproximateCreationDateTime": 1234567890,
                "SequenceNumber": "123456789012345678901",
            }
        }
        error_message = "Test error message"

        message = {
            "originalRecord": record,
            "errorMessage": error_message,
            "timestamp": record.get("dynamodb", {}).get("ApproximateCreationDateTime"),
            "sequenceNumber": record.get("dynamodb", {}).get("SequenceNumber"),
        }

        sqs_endpoint = "http://localhost:4566"
        sqs_url = "http://localhost:4566/queue/dlq"
        aws_region = "eu-west-2"

        with patch(
            "sqs.get_sqs_client", return_value=mock_sqs_client
        ) as mock_get_client:
            result = send_message_to_sqs(
                message=message,
                message_attributes={},
                sqs_endpoint=sqs_endpoint,
                sqs_url=sqs_url,
                aws_region=aws_region,
                logger=mock_logger,
            )

        assert result is True
        mock_get_client.assert_called_once_with(
            sqs_endpoint=sqs_endpoint, aws_region=aws_region, logger=mock_logger
        )

        mock_sqs_client.send_message.assert_called_once()
        mock_logger.info.assert_called_once_with(
            "Successfully sent message to SQS queue."
        )

    def test_send_message_failure(self):
        """
        Test that send_dynamodb_record_to_dlq returns False and logs an error when sending a message to the DLQ fails due to an exception.
        """
        mock_logger = MagicMock()
        mock_sqs_client = MagicMock()

        record = {
            "dynamodb": {
                "ApproximateCreationDateTime": 1234567890,
                "SequenceNumber": "123456789012345678901",
            }
        }
        error_message = "Test error message"

        message = {
            "originalRecord": record,
            "errorMessage": error_message,
            "timestamp": record.get("dynamodb", {}).get("ApproximateCreationDateTime"),
            "sequenceNumber": record.get("dynamodb", {}).get("SequenceNumber"),
        }

        sqs_endpoint = "http://localhost:4566"
        sqs_url = "http://localhost:4566/queue/dlq"
        aws_region = "eu-west-2"

        mock_sqs_client.send_message.side_effect = Exception("Connection error")
        with patch("sqs.get_sqs_client", return_value=mock_sqs_client):
            result = send_message_to_sqs(
                message=message,
                message_attributes={},
                sqs_endpoint=sqs_endpoint,
                sqs_url=sqs_url,
                aws_region=aws_region,
                logger=mock_logger,
            )

        assert result is False
        mock_logger.error.assert_called_once_with(
            "Failed to send message to SQS: Connection error"
        )
