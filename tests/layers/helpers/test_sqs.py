from unittest.mock import patch, MagicMock

import pytest

from sqs import get_sqs_client, send_dynamodb_record_to_dlq


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


class TestSendDynamoDbRecordToDLQ:
    def test_no_dlq_url(self, mock_sqs_client):
        """
        Test that send_dynamodb_record_to_dlq returns False when the DLQ URL is empty.
        """
        mock_logger = MagicMock()
        result = send_dynamodb_record_to_dlq(
            record={},
            sqs_endpoint="",
            dlq_url="",
            aws_region="",
            error_message="",
            logger=mock_logger,
        )

        assert result is False

    def test_send_message_success(self):
        """
        Tests that a DynamoDB record is successfully sent to the DLQ and logs the operation.

        Verifies that the SQS client is initialised with the correct parameters, the message is sent, and a success log entry is created.
        """
        mock_logger = MagicMock()
        mock_sqs_client = MagicMock()

        record = {
            "dynamodb": {
                "ApproximateCreationDateTime": 1234567890,
                "SequenceNumber": "123456789012345678901",
            }
        }
        sqs_endpoint = "http://localhost:4566"
        dlq_url = "http://localhost:4566/queue/dlq"
        aws_region = "eu-west-2"
        error_message = "Test error message"

        with patch(
            "sqs.get_sqs_client", return_value=mock_sqs_client
        ) as mock_get_client:
            result = send_dynamodb_record_to_dlq(
                record=record,
                sqs_endpoint=sqs_endpoint,
                dlq_url=dlq_url,
                aws_region=aws_region,
                error_message=error_message,
                logger=mock_logger,
            )

        assert result is True
        mock_get_client.assert_called_once_with(
            sqs_endpoint=sqs_endpoint, aws_region=aws_region, logger=mock_logger
        )

        mock_sqs_client.send_message.assert_called_once()
        mock_logger.info.assert_called_once_with(
            f"Successfully sent record to DLQ: {record.get('dynamodb', {}).get('SequenceNumber')}"
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
        sqs_endpoint = "http://localhost:4566"
        dlq_url = "http://localhost:4566/queue/dlq"
        aws_region = "eu-west-2"
        error_message = "Test error message"

        mock_sqs_client.send_message.side_effect = Exception("Connection error")
        with patch("sqs.get_sqs_client", return_value=mock_sqs_client):
            result = send_dynamodb_record_to_dlq(
                record=record,
                sqs_endpoint=sqs_endpoint,
                dlq_url=dlq_url,
                aws_region=aws_region,
                error_message=error_message,
                logger=mock_logger,
            )

        assert result is False
        mock_logger.error.assert_called_once_with(
            "Failed to send message to DLQ: Connection error"
        )
