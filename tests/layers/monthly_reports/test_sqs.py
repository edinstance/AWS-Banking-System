from unittest.mock import patch

from monthly_reports.sqs import send_continuation_message, send_bad_account_to_dlq


class TestSqsHelpers:

    def test_no_continuation_queue_url(self, mock_logger):

        result = send_continuation_message({}, "", [], {}, "", "", "", "", mock_logger)

        assert result is None
        assert mock_logger.error.call_count == 1
        assert (
            mock_logger.error.call_args[0][0]
            == "Cannot send continuation message: CONTINUATION_QUEUE_URL not set"
        )

    @patch("monthly_reports.sqs.send_message_to_sqs")
    def test_send_message_success(self, mock_send_sqs, mock_logger):
        """Test successful message sending with all data types"""
        scan_params = {"TableName": "accounts"}
        accounts = [{"accountId": "acc1", "userId": "user1"}]
        last_key = {"accountId": "acc123"}

        send_continuation_message(
            scan_params=scan_params,
            statement_period="2024-01",
            remaining_accounts=accounts,
            last_evaluated_key=last_key,
            continuation_type="batch_continuation",
            sqs_endpoint="https://sqs.us-east-1.amazonaws.com",
            continuation_queue_url="https://queue-url",
            aws_region="us-east-1",
            logger=mock_logger,
        )

        mock_send_sqs.assert_called_once()

        call_args = mock_send_sqs.call_args
        actual_message = call_args[1]["message"]
        expected_message = {
            "scan_params": scan_params,
            "statement_period": "2024-01",
            "remaining_accounts": accounts,
            "last_evaluated_key": last_key,
        }
        assert actual_message == expected_message

        expected_attributes = {
            "continuation_type": {
                "DataType": "String",
                "StringValue": "batch_continuation",
            }
        }
        assert call_args[1]["message_attributes"] == expected_attributes

    def test_send_bad_account_to_dlq_no_dlq_url(self, mock_logger):
        """Test warning when DLQ URL is not set"""
        result = send_bad_account_to_dlq(
            account={"accountId": "acc1"},
            statement_period="2024-01",
            error_reason="Test error",
            sqs_endpoint="https://sqs.us-east-1.amazonaws.com",
            dlq_url="",  # Empty DLQ URL
            aws_region="us-east-1",
            logger=mock_logger,
        )

        assert result is None
        mock_logger.warning.assert_called_once_with(
            "Cannot send bad account to DLQ: DLQ_URL not set"
        )

    @patch("monthly_reports.sqs.send_message_to_sqs")
    def test_send_bad_account_to_dlq_exception(self, mock_send_sqs, mock_logger):
        """Test exception handling when sending to DLQ fails"""
        mock_send_sqs.side_effect = Exception("SQS send failed")

        send_bad_account_to_dlq(
            account={"accountId": "acc1"},
            statement_period="2024-01",
            error_reason="Test error",
            sqs_endpoint="https://sqs.us-east-1.amazonaws.com",
            dlq_url="https://queue-url",
            aws_region="us-east-1",
            logger=mock_logger,
        )

        mock_logger.error.assert_called_once_with(
            "Failed to send bad account to DLQ: SQS send failed"
        )
