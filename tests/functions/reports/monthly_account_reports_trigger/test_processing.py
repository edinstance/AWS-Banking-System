import uuid
from unittest.mock import patch

from functions.reports.monthly_account_reports_trigger.monthly_account_reports_trigger.processing import (
    process_account_batch,
    chunk_accounts,
)


class TestProcessAccountBatch:

    def test_success(self, magic_mock_sfn_client, mock_logger):
        accounts_batch = [
            {"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())},
            {"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())},
        ]

        result = process_account_batch(
            accounts_batch, "2024-1", magic_mock_sfn_client, mock_logger, ""
        )

        assert result["processed"] == 2
        assert result["skipped"] == 0

    def test_invalid_account_mix(self, magic_mock_sfn_client, mock_logger):
        accounts_batch = [
            {},
            {"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())},
        ]

        result = process_account_batch(
            accounts_batch, "2024-1", magic_mock_sfn_client, mock_logger, ""
        )

        assert result["skipped"] == 1
        assert result["processed"] == 1

    def test_all_accounts_invalid(self, magic_mock_sfn_client, mock_logger):
        accounts_batch = [
            {},
        ]

        result = process_account_batch(
            accounts_batch, "2024-1", magic_mock_sfn_client, mock_logger, ""
        )

        assert result["skipped"] == 1

    def test_execution_already_exists(self, magic_mock_sfn_client, mock_logger):
        accounts_batch = [
            {"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())},
        ]

        with patch(
            "functions.reports.monthly_account_reports_trigger.monthly_account_reports_trigger.processing.start_sfn_execution_with_retry"
        ) as mock_start_sfn_execution_with_retry:
            mock_start_sfn_execution_with_retry.return_value = "already_exists"

            result = process_account_batch(
                accounts_batch, "2024-1", magic_mock_sfn_client, mock_logger, ""
            )

            assert result["already_exists"] == 1
            assert result["skipped"] == 0

    def test_failed_executions(self, magic_mock_sfn_client, mock_logger):
        accounts_batch = [
            {"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())},
        ]

        with patch(
            "functions.reports.monthly_account_reports_trigger.monthly_account_reports_trigger.processing.start_sfn_execution_with_retry"
        ) as mock_start_sfn_execution_with_retry:
            mock_start_sfn_execution_with_retry.return_value = "failed"

            result = process_account_batch(
                accounts_batch, "2024-1", magic_mock_sfn_client, mock_logger, ""
            )

            assert result["failed_starts"] == 1
            assert result["skipped"] == 0

    def test_exception_raised(self, magic_mock_sfn_client, mock_logger):
        accounts_batch = [
            {"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())},
        ]

        with patch(
            "functions.reports.monthly_account_reports_trigger.monthly_account_reports_trigger.processing.start_sfn_execution_with_retry"
        ) as mock_start_sfn_execution_with_retry:
            mock_start_sfn_execution_with_retry.side_effect = Exception(
                "Test exception"
            )

            result = process_account_batch(
                accounts_batch, "2024-1", magic_mock_sfn_client, mock_logger, ""
            )

            assert result["failed_starts"] == 1
            assert result["skipped"] == 0


class TestChunkAccounts:

    def test_chunk_accounts_basic(self):
        accounts = list(range(20))
        chunks = list(chunk_accounts(accounts, chunk_size=10))

        assert len(chunks) == 2
        assert chunks[0] == list(range(10))
        assert chunks[1] == list(range(10, 20))

    def test_chunk_accounts_smaller_than_chunk_size(self):
        accounts = [1, 2, 3]
        chunks = list(chunk_accounts(accounts, chunk_size=10))

        assert len(chunks) == 1
        assert chunks[0] == [1, 2, 3]

    def test_chunk_accounts_empty_list(self):
        accounts = []
        chunks = list(chunk_accounts(accounts, chunk_size=10))

        assert len(chunks) == 0

    def test_chunk_accounts_custom_chunk_size(self):
        accounts = list(range(7))
        chunks = list(chunk_accounts(accounts, chunk_size=3))

        assert len(chunks) == 3
        assert chunks[0] == [0, 1, 2]
        assert chunks[1] == [3, 4, 5]
        assert chunks[2] == [6]
