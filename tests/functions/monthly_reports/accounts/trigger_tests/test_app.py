import json
from importlib import reload
from unittest.mock import MagicMock, patch

import pytest

from functions.monthly_reports.accounts.trigger.trigger import app
from functions.monthly_reports.accounts.trigger.trigger.app import (
    lambda_handler,
)


class TestLambdaHandler:
    def test_success(self, monthly_accounts_reports_app_with_mocks):

        mock_event = {}
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000

        with patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.get_paginated_table_data"
        ) as mock_get_data, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.process_account_batch"
        ) as mock_process_batch:
            mock_get_data.return_value = [
                {"accountId": "acc1", "userId": "user1"},
                {"accountId": "acc2", "userId": "user2"},
                {"accountId": "acc3", "userId": "user3"},
            ], {}

            mock_process_batch.return_value = {
                "processed": 3,
                "failed_starts": 0,
                "skipped": 0,
                "already_exists": 0,
            }

            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["message"] == "Monthly Account reports processing completed"
            assert body["totalAccountsProcessed"] == 3
            assert body["processed_count"] == 3
            assert body["batches_processed"] == 1

    def test_timeout_warning(
        self, monthly_accounts_reports_app_with_mocks, mock_logger
    ):
        mock_event = {}
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 10

        with patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.logger"
        ) as mock_logger_instance, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.get_paginated_table_data"
        ) as mock_get_data, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.process_account_batch"
        ) as mock_process_batch:

            mock_get_data.return_value = [
                {"accountId": "acc1", "userId": "user1"},
            ], {}

            mock_process_batch.return_value = {
                "processed": 0,
                "failed_starts": 0,
                "skipped": 0,
                "already_exists": 0,
            }

            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 202
            body = json.loads(response["body"])
            assert (
                body["message"]
                == "Monthly Account reports processing timeout_continuation"
            )
            assert body["totalAccountsProcessed"] == 0
            assert body["processed_count"] == 0
            assert body["batches_processed"] == 0

            mock_logger_instance.warning.assert_called_once()
            warning_call_args = mock_logger_instance.warning.call_args[0][0]
            assert "Approaching Lambda timeout" in warning_call_args

    def test_critical_error_during_batch_processing_raises_exception(
        self, monthly_accounts_reports_app_with_mocks
    ):
        mock_event = {}
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000

        with patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.get_paginated_table_data"
        ) as mock_get_data:
            mock_get_data.side_effect = Exception("Database connection failed")

            with pytest.raises(Exception, match="Database connection failed"):
                lambda_handler(mock_event, mock_context)

    def test_batch_processing_exception_continues_processing(
        self, monthly_accounts_reports_app_with_mocks
    ):
        mock_event = {}
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000

        with patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.get_paginated_table_data"
        ) as mock_get_data, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.process_account_batch"
        ) as mock_process_batch, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.logger"
        ) as mock_logger:
            mock_get_data.return_value = [
                {"accountId": "acc1", "userId": "user1"},
                {"accountId": "acc2", "userId": "user2"},
                {"accountId": "acc3", "userId": "user3"},
                {"accountId": "acc4", "userId": "user4"},
                {"accountId": "acc5", "userId": "user5"},
                {"accountId": "acc6", "userId": "user6"},
                {"accountId": "acc7", "userId": "user7"},
                {"accountId": "acc8", "userId": "user8"},
                {"accountId": "acc9", "userId": "user9"},
                {"accountId": "acc10", "userId": "user10"},
                {"accountId": "acc11", "userId": "user11"},
            ], {}

            mock_process_batch.side_effect = [
                Exception("Batch processing failed"),
                {"processed": 1, "failed_starts": 0, "skipped": 0, "already_exists": 0},
            ]

            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])

            assert body["totalAccountsProcessed"] == 11
            assert body["failed_starts_count"] == 10
            assert body["processed_count"] == 1
            assert body["batches_processed"] == 1

            mock_logger.error.assert_called_once()
            error_call_args = mock_logger.error.call_args[0][0]
            assert "Error processing batch 1" in error_call_args

    def test_no_accounts_pages_left(self, monthly_accounts_reports_app_with_mocks):

        mock_event = {}
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000

        with patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.get_paginated_table_data"
        ) as mock_get_data, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.process_account_batch"
        ) as mock_process_batch, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.logger"
        ) as mock_logger:
            mock_get_data.side_effect = [
                (
                    [
                        {"accountId": "acc1", "userId": "user1"},
                        {"accountId": "acc2", "userId": "user2"},
                        {"accountId": "acc3", "userId": "user3"},
                        {"accountId": "acc4", "userId": "user4"},
                        {"accountId": "acc5", "userId": "user5"},
                        {"accountId": "acc6", "userId": "user6"},
                        {"accountId": "acc7", "userId": "user7"},
                        {"accountId": "acc8", "userId": "user8"},
                        {"accountId": "acc9", "userId": "user9"},
                        {"accountId": "acc10", "userId": "user10"},
                    ],
                    {"LastEvaluatedKey": "some_key"},
                ),
                ([], {}),
            ]

            mock_process_batch.return_value = {
                "processed": 10,
                "failed_starts": 0,
                "skipped": 0,
                "already_exists": 0,
            }

            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["totalAccountsProcessed"] == 10
            assert body["processed_count"] == 10
            assert body["batches_processed"] == 1

            mock_logger.info.assert_any_call("No more accounts to process")

    def test_timeout_during_batch_processing_with_continuation(
        self, monthly_accounts_reports_app_with_mocks, monkeypatch
    ):
        mock_event = {}
        mock_context = MagicMock()

        remaining_times = [60000, 50000, 25000]
        mock_context.get_remaining_time_in_millis.side_effect = remaining_times

        with patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.get_paginated_table_data"
        ) as mock_get_data, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.process_account_batch"
        ) as mock_process_batch, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.send_message_to_sqs"
        ) as mock_send_sqs, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.logger"
        ) as mock_logger:
            mock_get_data.return_value = (
                [{"accountId": f"acc{i}", "userId": f"user{i}"} for i in range(1, 21)],
                {"LastEvaluatedKey": "continuation_key"},
            )

            mock_process_batch.return_value = {
                "processed": 10,
                "failed_starts": 0,
                "skipped": 0,
                "already_exists": 0,
            }

            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 202
            body = json.loads(response["body"])
            assert (
                body["message"]
                == "Monthly Account reports processing timeout_continuation"
            )
            assert body["status"] == "TIMEOUT_CONTINUATION"

            assert body["totalAccountsProcessed"] == 10
            assert body["processed_count"] == 10
            assert body["batches_processed"] == 1
            assert body["pages_processed"] == 1

            mock_logger.warning.assert_called()
            warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
            timeout_warning = any(
                "Timeout approaching during batch processing" in msg
                for msg in warning_calls
            )
            assert timeout_warning

            mock_send_sqs.assert_called_once()
            sqs_call_args = mock_send_sqs.call_args
            message_body = sqs_call_args[1]["message"]

            assert "scan_params" in message_body
            assert "last_evaluated_key" in message_body
            assert "statement_period" in message_body
            assert "remaining_accounts" in message_body
            assert message_body["last_evaluated_key"] == {
                "LastEvaluatedKey": "continuation_key"
            }

            assert len(message_body["remaining_accounts"]) == 10

            message_attributes = sqs_call_args[1]["message_attributes"]
            assert (
                message_attributes["continuation_type"]["StringValue"]
                == "batch_continuation"
            )

    def test_missing_queue_url(
        self, monthly_accounts_reports_app_with_mocks, monkeypatch
    ):
        monkeypatch.delenv("CONTINUATION_QUEUE_URL", raising=False)
        reload(app)

        mock_event = {}
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000

        with patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.get_paginated_table_data"
        ) as mock_get_data, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.process_account_batch"
        ) as mock_process_batch:
            mock_get_data.return_value = [
                {"accountId": "acc1", "userId": "user1"},
                {"accountId": "acc2", "userId": "user2"},
                {"accountId": "acc3", "userId": "user3"},
            ], {}

            mock_process_batch.return_value = {
                "processed": 3,
                "failed_starts": 0,
                "skipped": 0,
                "already_exists": 0,
            }

            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 500
            body = json.loads(response["body"])
            assert (
                body["message"]
                == "Monthly Account reports processing error_no_continuation_queue"
            )
