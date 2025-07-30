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
            "functions.monthly_reports.accounts.trigger.trigger.app.process_accounts_page"
        ) as mock_process_page:
            mock_get_data.return_value = [
                {"accountId": "acc1", "userId": "user1"},
                {"accountId": "acc2", "userId": "user2"},
                {"accountId": "acc3", "userId": "user3"},
            ], {}

            mock_process_page.return_value = {
                "processed_count": 3,
                "failed_starts_count": 0,
                "skipped_count": 0,
                "already_exists_count": 0,
                "batches_processed": 1,
                "status": "COMPLETED",
            }

            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 200
            # The response body is already a dict, not a JSON string
            body = (
                response["body"]
                if isinstance(response["body"], dict)
                else json.loads(response["body"])
            )
            assert body["message"] == "Monthly Account reports processing completed"
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
        ) as mock_logger_instance:
            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 202
            body = (
                response["body"]
                if isinstance(response["body"], dict)
                else json.loads(response["body"])
            )
            assert (
                body["message"]
                == "Monthly Account reports processing timeout_continuation"
            )
            assert body["processed_count"] == 0
            assert body["pages_processed"] == 0

            mock_logger_instance.warning.assert_called_once()
            warning_call_args = mock_logger_instance.warning.call_args[0][0]
            assert "Approaching Lambda timeout" in warning_call_args

    def test_critical_error_during_data_retrieval_raises_exception(
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

    def test_page_processing_with_timeout_continuation(
        self, monthly_accounts_reports_app_with_mocks
    ):
        mock_event = {}
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 10

        with patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.get_paginated_table_data"
        ) as mock_get_data, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.process_accounts_page"
        ) as mock_process_page, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.send_continuation_message"
        ) as mock_send_continuation:
            mock_get_data.return_value = [
                {"accountId": f"acc{i}", "userId": f"user{i}"} for i in range(1, 11)
            ], {}

            mock_process_page.return_value = {
                "processed_count": 5,
                "failed_starts_count": 0,
                "skipped_count": 0,
                "already_exists_count": 0,
                "batches_processed": 1,
                "status": "TIMEOUT_CONTINUATION",
                "remaining_accounts": [
                    {"accountId": f"acc{i}", "userId": f"user{i}"} for i in range(6, 11)
                ],
            }

            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 202
            body = (
                response["body"]
                if isinstance(response["body"], dict)
                else json.loads(response["body"])
            )
            assert body["status"] == "TIMEOUT_CONTINUATION"

            mock_send_continuation.assert_called_once()

    def test_no_accounts_pages_left(self, monthly_accounts_reports_app_with_mocks):
        mock_event = {}
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000

        with patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.get_paginated_table_data"
        ) as mock_get_data, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.process_accounts_page"
        ) as mock_process_page, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.logger"
        ) as mock_logger:
            mock_get_data.side_effect = [
                (
                    [
                        {"accountId": f"acc{i}", "userId": f"user{i}"}
                        for i in range(1, 11)
                    ],
                    {"LastEvaluatedKey": "some_key"},
                ),
                ([], {}),
            ]

            mock_process_page.return_value = {
                "processed_count": 10,
                "failed_starts_count": 0,
                "skipped_count": 0,
                "already_exists_count": 0,
                "batches_processed": 1,
                "status": "COMPLETED",
            }

            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 200
            body = (
                response["body"]
                if isinstance(response["body"], dict)
                else json.loads(response["body"])
            )
            assert body["processed_count"] == 10
            assert body["batches_processed"] == 1

            mock_logger.info.assert_any_call("No more accounts to process")

    def test_multiple_pages_processing(self, monthly_accounts_reports_app_with_mocks):
        mock_event = {}
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000

        with patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.get_paginated_table_data"
        ) as mock_get_data, patch(
            "functions.monthly_reports.accounts.trigger.trigger.app.process_accounts_page"
        ) as mock_process_page:
            # Simulate multiple pages
            mock_get_data.side_effect = [
                (
                    [
                        {"accountId": f"acc{i}", "userId": f"user{i}"}
                        for i in range(1, 6)
                    ],
                    {"LastEvaluatedKey": "key1"},
                ),
                (
                    [
                        {"accountId": f"acc{i}", "userId": f"user{i}"}
                        for i in range(6, 11)
                    ],
                    {},
                ),
            ]

            mock_process_page.side_effect = [
                {
                    "processed_count": 5,
                    "failed_starts_count": 0,
                    "skipped_count": 0,
                    "already_exists_count": 0,
                    "batches_processed": 1,
                    "status": "COMPLETED",
                },
                {
                    "processed_count": 5,
                    "failed_starts_count": 0,
                    "skipped_count": 0,
                    "already_exists_count": 0,
                    "batches_processed": 1,
                    "status": "COMPLETED",
                },
            ]

            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 200
            body = (
                response["body"]
                if isinstance(response["body"], dict)
                else json.loads(response["body"])
            )
            assert body["processed_count"] == 10
            assert body["batches_processed"] == 2
            assert body["pages_processed"] == 2

    def test_missing_queue_url(
        self, monthly_accounts_reports_app_with_mocks, monkeypatch
    ):
        monkeypatch.delenv("CONTINUATION_QUEUE_URL", raising=False)
        reload(app)

        mock_event = {}
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000

        response = lambda_handler(mock_event, mock_context)

        assert response["statusCode"] == 500
        body = (
            response["body"]
            if isinstance(response["body"], dict)
            else json.loads(response["body"])
        )
        assert (
            body["message"]
            == "Monthly Account reports processing error_no_continuation_queue"
        )
