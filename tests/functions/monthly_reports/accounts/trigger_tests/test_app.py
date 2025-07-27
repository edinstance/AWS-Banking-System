import json
from unittest.mock import MagicMock, patch

import pytest

from functions.monthly_reports.accounts.trigger.trigger.app import (
    lambda_handler,
)


class TestLambdaHandler:
    def test_success(self, monthly_accounts_reports_app_with_mocks):

        mock_event = {}
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000

        with patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.get_all_table_data"
        ) as mock_get_data, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.process_account_batch"
        ) as mock_process_batch:
            mock_get_data.return_value = [
                {"accountId": "acc1", "userId": "user1"},
                {"accountId": "acc2", "userId": "user2"},
                {"accountId": "acc3", "userId": "user3"},
            ]

            mock_process_batch.return_value = {
                "processed": 3,
                "failed_starts": 0,
                "skipped": 0,
                "already_exists": 0,
            }

            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert (
                body["message"] == "Monthly Account monthly_reports initiation complete"
            )
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
            "functions.monthly_reports.accounts.trigger.trigger.app.get_all_table_data"
        ) as mock_get_data, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.process_account_batch"
        ) as mock_process_batch:

            mock_get_data.return_value = [
                {"accountId": "acc1", "userId": "user1"},
            ]

            mock_process_batch.return_value = {
                "processed": 0,
                "failed_starts": 0,
                "skipped": 0,
                "already_exists": 0,
            }

            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert (
                body["message"] == "Monthly Account monthly_reports initiation complete"
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
            "functions.monthly_reports.accounts.trigger.trigger.app.get_all_table_data"
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
            "functions.monthly_reports.accounts.trigger.trigger.app.get_all_table_data"
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
            ]

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
            assert "Unexpected error processing batch 1" in error_call_args
