import json
from importlib import reload
from unittest.mock import MagicMock, patch

import pytest

from functions.monthly_reports.accounts.process_pending_reports.process_pending_reports import (
    app,
)
from functions.monthly_reports.accounts.process_pending_reports.process_pending_reports.app import (
    lambda_handler,
)


class TestLambdaHandler:
    def test_accounts_scan_continuation_success(
        self, monthly_reports_continuation_app_with_mocks
    ):
        mock_event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "scan_params": {
                                "ProjectionExpression": "accountId, userId"
                            },
                            "statement_period": "2024-01",
                        }
                    ),
                    "messageAttributes": {
                        "continuation_type": {"stringValue": "accounts_scan"}
                    },
                }
            ]
        }
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000

        with patch(
            "functions.monthly_reports.accounts.process_pending_reports.process_pending_reports.app.process_accounts_scan_continuation"
        ) as mock_process_scan:
            mock_process_scan.return_value = {
                "processed_count": 5,
                "failed_starts_count": 0,
                "skipped_count": 0,
                "already_exists_count": 0,
                "batches_processed": 1,
                "pages_processed": 1,
                "status": "COMPLETED",
            }

            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 200
            body = (
                response["body"]
                if isinstance(response["body"], dict)
                else json.loads(response["body"])
            )
            assert body["message"] == "Monthly Account reports processing completed"
            assert body["processed_count"] == 5
            assert body["batches_processed"] == 1

            mock_process_scan.assert_called_once_with(
                {"ProjectionExpression": "accountId, userId"},
                "2024-01",
                mock_context,
                app.logger,
                app.accounts_table,
                app.sfn_client,
                app.STATE_MACHINE_ARN,
                app.SQS_ENDPOINT,
                app.CONTINUATION_QUEUE_URL,
                app.AWS_REGION,
                app.PAGE_SIZE,
                app.BATCH_SIZE,
                app.SAFETY_BUFFER,
            )

    def test_batch_continuation_success(
        self, monthly_reports_continuation_app_with_mocks
    ):
        mock_event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "scan_params": {
                                "ProjectionExpression": "accountId, userId"
                            },
                            "statement_period": "2024-01",
                            "remaining_accounts": [
                                {"accountId": "acc1", "userId": "user1"},
                                {"accountId": "acc2", "userId": "user2"},
                            ],
                            "last_evaluated_key": {"accountId": "acc_last"},
                        }
                    ),
                    "messageAttributes": {
                        "continuation_type": {"stringValue": "batch_continuation"}
                    },
                }
            ]
        }
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000

        with patch(
            "functions.monthly_reports.accounts.process_pending_reports.process_pending_reports.app.process_batch_continuation"
        ) as mock_process_batch:
            mock_process_batch.return_value = {
                "processed_count": 2,
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
            assert body["message"] == "Monthly Account reports processing completed"
            assert body["processed_count"] == 2

            mock_process_batch.assert_called_once_with(
                {"ProjectionExpression": "accountId, userId"},
                "2024-01",
                [
                    {"accountId": "acc1", "userId": "user1"},
                    {"accountId": "acc2", "userId": "user2"},
                ],
                {"accountId": "acc_last"},
                mock_context,
                app.logger,
                app.accounts_table,
                app.sfn_client,
                app.STATE_MACHINE_ARN,
                app.SQS_ENDPOINT,
                app.CONTINUATION_QUEUE_URL,
                app.AWS_REGION,
                app.PAGE_SIZE,
                app.BATCH_SIZE,
                app.SAFETY_BUFFER,
            )

    def test_batch_continuation_without_last_evaluated_key(
        self, monthly_reports_continuation_app_with_mocks
    ):
        mock_event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "scan_params": {
                                "ProjectionExpression": "accountId, userId"
                            },
                            "statement_period": "2024-01",
                            "remaining_accounts": [
                                {"accountId": "acc1", "userId": "user1"}
                            ],
                        }
                    ),
                    "messageAttributes": {
                        "continuation_type": {"stringValue": "batch_continuation"}
                    },
                }
            ]
        }
        mock_context = MagicMock()

        with patch(
            "functions.monthly_reports.accounts.process_pending_reports.process_pending_reports.app.process_batch_continuation"
        ) as mock_process_batch:
            mock_process_batch.return_value = {
                "processed_count": 1,
                "failed_starts_count": 0,
                "skipped_count": 0,
                "already_exists_count": 0,
                "batches_processed": 1,
                "status": "COMPLETED",
            }

            lambda_handler(mock_event, mock_context)

            mock_process_batch.assert_called_once()
            call_args = mock_process_batch.call_args[0]
            assert call_args[3] is None

    def test_unknown_continuation_type(
        self, monthly_reports_continuation_app_with_mocks
    ):
        mock_event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "scan_params": {
                                "ProjectionExpression": "accountId, userId"
                            },
                            "statement_period": "2024-01",
                        }
                    ),
                    "messageAttributes": {
                        "continuation_type": {"stringValue": "unknown_type"}
                    },
                }
            ]
        }
        mock_context = MagicMock()

        with patch(
            "functions.monthly_reports.accounts.process_pending_reports.process_pending_reports.app.logger"
        ) as mock_logger:
            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 200
            mock_logger.warning.assert_called_once_with(
                "Unknown continuation type: unknown_type"
            )

    def test_missing_continuation_type(
        self, monthly_reports_continuation_app_with_mocks
    ):
        mock_event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "scan_params": {
                                "ProjectionExpression": "accountId, userId"
                            },
                            "statement_period": "2024-01",
                        }
                    ),
                    "messageAttributes": {},
                }
            ]
        }
        mock_context = MagicMock()

        with patch(
            "functions.monthly_reports.accounts.process_pending_reports.process_pending_reports.app.logger"
        ) as mock_logger:
            response = lambda_handler(mock_event, mock_context)

            assert response["statusCode"] == 200
            mock_logger.warning.assert_called_once_with(
                "Unknown continuation type: None"
            )

    def test_multiple_sqs_records(self, monthly_reports_continuation_app_with_mocks):
        mock_event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "scan_params": {
                                "ProjectionExpression": "accountId, userId"
                            },
                            "statement_period": "2024-01",
                        }
                    ),
                    "messageAttributes": {
                        "continuation_type": {"stringValue": "accounts_scan"}
                    },
                },
                {
                    "body": json.dumps(
                        {
                            "scan_params": {
                                "ProjectionExpression": "accountId, userId"
                            },
                            "statement_period": "2024-01",
                            "remaining_accounts": [
                                {"accountId": "acc1", "userId": "user1"}
                            ],
                        }
                    ),
                    "messageAttributes": {
                        "continuation_type": {"stringValue": "batch_continuation"}
                    },
                },
            ]
        }
        mock_context = MagicMock()

        with patch(
            "functions.monthly_reports.accounts.process_pending_reports.process_pending_reports.app.process_accounts_scan_continuation"
        ) as mock_process_scan, patch(
            "functions.monthly_reports.accounts.process_pending_reports.process_pending_reports.app.process_batch_continuation"
        ) as mock_process_batch:
            mock_process_scan.return_value = {
                "processed_count": 3,
                "failed_starts_count": 0,
                "skipped_count": 0,
                "already_exists_count": 0,
                "batches_processed": 1,
                "pages_processed": 1,
                "status": "COMPLETED",
            }
            mock_process_batch.return_value = {
                "processed_count": 1,
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
            assert body["processed_count"] == 4
            assert body["batches_processed"] == 2

            mock_process_scan.assert_called_once()
            mock_process_batch.assert_called_once()

    def test_empty_records_list(self, monthly_reports_continuation_app_with_mocks):
        mock_event = {"Records": []}
        mock_context = MagicMock()

        response = lambda_handler(mock_event, mock_context)

        assert response["statusCode"] == 200
        body = (
            response["body"]
            if isinstance(response["body"], dict)
            else json.loads(response["body"])
        )
        assert body["processed_count"] == 0
        assert body["batches_processed"] == 0

    def test_missing_records_key(self, monthly_reports_continuation_app_with_mocks):
        mock_event = {}
        mock_context = MagicMock()

        response = lambda_handler(mock_event, mock_context)

        assert response["statusCode"] == 200
        body = (
            response["body"]
            if isinstance(response["body"], dict)
            else json.loads(response["body"])
        )
        assert body["processed_count"] == 0

    def test_critical_error_during_processing_raises_exception(
        self, monthly_reports_continuation_app_with_mocks
    ):
        mock_event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "scan_params": {
                                "ProjectionExpression": "accountId, userId"
                            },
                            "statement_period": "2024-01",
                        }
                    ),
                    "messageAttributes": {
                        "continuation_type": {"stringValue": "accounts_scan"}
                    },
                }
            ]
        }
        mock_context = MagicMock()

        with patch(
            "functions.monthly_reports.accounts.process_pending_reports.process_pending_reports.app.process_accounts_scan_continuation"
        ) as mock_process_scan:
            mock_process_scan.side_effect = Exception("Processing failed")

            with pytest.raises(Exception, match="Processing failed"):
                lambda_handler(mock_event, mock_context)

    def test_invalid_json_in_message_body_raises_exception(
        self, monthly_reports_continuation_app_with_mocks
    ):
        mock_event = {
            "Records": [
                {
                    "body": "invalid json",
                    "messageAttributes": {
                        "continuation_type": {"stringValue": "accounts_scan"}
                    },
                }
            ]
        }
        mock_context = MagicMock()

        with patch(
                "functions.monthly_reports.accounts.process_pending_reports.process_pending_reports.app.logger"
        ) as mock_logger:

            lambda_handler(mock_event, mock_context)

            mock_logger.error.assert_called_once()

            error_call_args = mock_logger.error.call_args[0][0]
            assert "Failed to parse message body as JSON" in error_call_args

    def test_missing_accounts_table_name(self, monkeypatch):
        monkeypatch.delenv("ACCOUNTS_TABLE_NAME", raising=False)
        monkeypatch.setenv(
            "CONTINUATION_QUEUE_URL",
            "https://sqs.eu-west-2.amazonaws.com/123456789012/continuation-queue",
        )
        reload(app)

        mock_event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "scan_params": {
                                "ProjectionExpression": "accountId, userId"
                            },
                            "statement_period": "2024-01",
                        }
                    ),
                    "messageAttributes": {
                        "continuation_type": {"stringValue": "accounts_scan"}
                    },
                }
            ]
        }
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 300000

        with pytest.raises(Exception):
            lambda_handler(mock_event, mock_context)

    def test_environment_variables_initialization(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT_NAME", "production")
        monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        reload(app)

        assert app.ENVIRONMENT_NAME == "production"
        assert app.POWERTOOLS_LOG_LEVEL == "DEBUG"
        assert app.AWS_REGION == "us-east-1"

    def test_constants_are_set(self):
        assert app.PAGE_SIZE == 50
        assert app.BATCH_SIZE == 10
        assert app.SAFETY_BUFFER == 30

    def test_lambda_handler_logger_injection(
        self, monthly_reports_continuation_app_with_mocks
    ):
        mock_event = {"Records": []}
        mock_context = MagicMock()

        with patch(
            "functions.monthly_reports.accounts.process_pending_reports.process_pending_reports.app.logger"
        ) as mock_logger:
            response = lambda_handler(mock_event, mock_context)

            mock_logger.info.assert_any_call("Processing SQS continuation messages")
            assert response["statusCode"] == 200
