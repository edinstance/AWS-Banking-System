import uuid
from unittest.mock import patch, MagicMock

from monthly_reports.processing import (
    process_account_batch,
    chunk_accounts,
    process_batch_continuation,
    process_accounts_scan_continuation,
    process_account_batches,
    process_accounts_page,
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

        process_account_batch(
            accounts_batch, "2024-1", magic_mock_sfn_client, mock_logger, ""
        )

    @patch("monthly_reports.processing.send_bad_account_to_dlq")
    def test_invalid_account_with_dlq_parameters(
        self, mock_send_dlq, magic_mock_sfn_client, mock_logger
    ):
        accounts_batch = [
            {"accountId": "", "userId": ""},
        ]

        result = process_account_batch(
            accounts_batch,
            "2024-1",
            magic_mock_sfn_client,
            mock_logger,
            "",
            sqs_endpoint="https://sqs.amazonaws.com",
            dlq_url="https://sqs.amazonaws.com/queue/dlq",
            aws_region="us-east-1",
        )

        assert result["skipped"] == 1
        mock_send_dlq.assert_called_once()

    def test_execution_already_exists(self, magic_mock_sfn_client, mock_logger):
        accounts_batch = [
            {"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())},
        ]

        with patch(
            "monthly_reports.processing.start_sfn_execution_with_retry"
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
            "monthly_reports.processing.start_sfn_execution_with_retry"
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
            "monthly_reports.processing.start_sfn_execution_with_retry"
        ) as mock_start_sfn_execution_with_retry:
            mock_start_sfn_execution_with_retry.side_effect = Exception(
                "Test exception"
            )

            result = process_account_batch(
                accounts_batch, "2024-1", magic_mock_sfn_client, mock_logger, ""
            )

            assert result["failed_starts"] == 1
            assert result["skipped"] == 0

    @patch("monthly_reports.processing.send_bad_account_to_dlq")
    def test_failed_executions_with_dlq(
        self, mock_send_dlq, magic_mock_sfn_client, mock_logger
    ):
        accounts_batch = [
            {"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())},
        ]

        with patch(
            "monthly_reports.processing.start_sfn_execution_with_retry"
        ) as mock_start_sfn_execution_with_retry:
            mock_start_sfn_execution_with_retry.return_value = "failed"

            result = process_account_batch(
                accounts_batch,
                "2024-1",
                magic_mock_sfn_client,
                mock_logger,
                "",
                sqs_endpoint="https://sqs.amazonaws.com",
                dlq_url="https://sqs.amazonaws.com/queue/dlq",
                aws_region="us-east-1",
            )

            assert result["failed_starts"] == 1
            assert result["skipped"] == 0
            mock_send_dlq.assert_called_once()

    @patch("monthly_reports.processing.send_bad_account_to_dlq")
    def test_exception_raised_with_dlq(
        self, mock_send_dlq, magic_mock_sfn_client, mock_logger
    ):
        accounts_batch = [
            {"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())},
        ]

        with patch(
            "monthly_reports.processing.start_sfn_execution_with_retry"
        ) as mock_start_sfn_execution_with_retry:
            mock_start_sfn_execution_with_retry.side_effect = Exception(
                "Test exception"
            )

            result = process_account_batch(
                accounts_batch,
                "2024-1",
                magic_mock_sfn_client,
                mock_logger,
                "",
                sqs_endpoint="https://sqs.amazonaws.com",
                dlq_url="https://sqs.amazonaws.com/queue/dlq",
                aws_region="us-east-1",
            )

            assert result["failed_starts"] == 1
            assert result["skipped"] == 0
            mock_send_dlq.assert_called_once()


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


class TestProcessAccountsPage:

    @patch("monthly_reports.processing.process_account_batches")
    @patch("monthly_reports.processing.initialize_metrics")
    def test_process_accounts_page_success(
        self, mock_initialize_metrics, mock_process_batches, mock_logger
    ):
        mock_initialize_metrics.return_value = {"processed_count": 0}
        mock_process_batches.return_value = {"processed_count": 5}

        accounts_page = [
            {"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())}
            for _ in range(15)
        ]

        with patch("monthly_reports.processing.merge_metrics") as mock_merge:
            result = process_accounts_page(
                accounts_page=accounts_page,
                statement_period="2024-1",
                context=MagicMock(),
                logger=mock_logger,
                sfn_client=MagicMock(),
                state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:test",
                scan_params={},
                last_evaluated_key=None,
                sqs_endpoint="https://sqs.us-east-1.amazonaws.com",
                continuation_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
                aws_region="us-east-1",
                batch_size=10,
            )

            mock_process_batches.assert_called_once()
            mock_merge.assert_called_once()
            assert result == {"processed_count": 0}


class TestProcessAccountBatches:

    def test_process_account_batches_success(self, mock_logger):
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 60000  # 60 seconds

        account_batches = [
            [{"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())}],
            [{"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())}],
        ]

        with patch(
            "monthly_reports.processing.process_account_batch"
        ) as mock_process_batch:
            mock_process_batch.return_value = {"processed": 1, "skipped": 0}

            with patch(
                "monthly_reports.processing.initialize_metrics"
            ) as mock_init_metrics:
                mock_init_metrics.return_value = {
                    "processed_count": 0,
                    "skipped_count": 0,
                    "batches_processed": 0,
                    "failed_starts_count": 0,
                }

                result = process_account_batches(
                    account_batches=account_batches,
                    statement_period="2024-1",
                    context=mock_context,
                    logger=mock_logger,
                    sfn_client=MagicMock(),
                    state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:test",
                    scan_params={},
                    last_evaluated_key=None,
                    sqs_endpoint="https://sqs.us-east-1.amazonaws.com",
                    continuation_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
                    aws_region="us-east-1",
                )

                assert result["processed_count"] == 2
                assert result["batches_processed"] == 2
                assert mock_process_batch.call_count == 2

    def test_process_account_batches_timeout_approaching(self, mock_logger):
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 20000  # 20 seconds

        account_batches = [
            [{"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())}],
            [{"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())}],
        ]

        with patch(
            "monthly_reports.processing.send_continuation_message"
        ) as mock_send_continuation:
            with patch(
                "monthly_reports.processing.initialize_metrics"
            ) as mock_init_metrics:
                mock_init_metrics.return_value = {
                    "processed_count": 0,
                    "skipped_count": 0,
                    "batches_processed": 0,
                    "failed_starts_count": 0,
                }

                result = process_account_batches(
                    account_batches=account_batches,
                    statement_period="2024-1",
                    context=mock_context,
                    logger=mock_logger,
                    sfn_client=MagicMock(),
                    state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:test",
                    scan_params={},
                    last_evaluated_key={"id": "test"},
                    sqs_endpoint="https://sqs.us-east-1.amazonaws.com",
                    continuation_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
                    aws_region="us-east-1",
                    safety_buffer=30,
                )

                mock_send_continuation.assert_called_once()
                assert result["batches_processed"] == 0

    def test_process_account_batches_exception_handling(self, mock_logger):
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 60000

        account_batches = [
            [{"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())}],
        ]

        with patch(
            "monthly_reports.processing.process_account_batch"
        ) as mock_process_batch:
            mock_process_batch.side_effect = Exception("Test exception")

            with patch(
                "monthly_reports.processing.initialize_metrics"
            ) as mock_init_metrics:
                mock_init_metrics.return_value = {
                    "processed_count": 0,
                    "skipped_count": 0,
                    "batches_processed": 0,
                    "failed_starts_count": 0,
                }

                with patch(
                    "monthly_reports.processing.send_bad_account_to_dlq"
                ) as mock_send_to_dlq:
                    result = process_account_batches(
                        account_batches=account_batches,
                        statement_period="2024-1",
                        context=mock_context,
                        logger=mock_logger,
                        sfn_client=MagicMock(),
                        state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:test",
                        scan_params={},
                        last_evaluated_key=None,
                        sqs_endpoint="https://sqs.us-east-1.amazonaws.com",
                        continuation_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
                        aws_region="us-east-1",
                        dlq_url="https://sqs.us-east-1.amazonaws.com/123456789012/dlq-queue",
                    )

                    assert result["failed_starts_count"] == 1
                    assert result["batches_processed"] == 0

                    mock_send_to_dlq.assert_called_once()
                    call_args = mock_send_to_dlq.call_args[0]
                    assert call_args[0] == account_batches[0][0]
                    assert call_args[1] == "2024-1"
                    assert "Batch processing exception: Test exception" in call_args[2]


class TestProcessAccountsScanContinuation:

    @patch("monthly_reports.processing.merge_metrics")
    @patch("monthly_reports.processing.initialize_metrics")
    @patch("monthly_reports.processing.process_accounts_page")
    @patch("monthly_reports.processing.get_paginated_table_data")
    def test_process_accounts_scan_continuation_success(
        self,
        mock_get_paginated_data,
        mock_process_page,
        mock_initialize_metrics,
        mock_merge_metrics,
        mock_logger,
    ):
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 60000

        mock_initialize_metrics.return_value = {"pages_processed": 0}
        mock_get_paginated_data.side_effect = [
            ([{"accountId": "123", "userId": "456"}], {"id": "next"}),
            ([], None),
        ]
        mock_process_page.return_value = {"processed_count": 1}

        result = process_accounts_scan_continuation(
            scan_params={},
            statement_period="2024-1",
            context=mock_context,
            logger=mock_logger,
            accounts_table=MagicMock(),
            sfn_client=MagicMock(),
            state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:test",
            sqs_endpoint="https://sqs.us-east-1.amazonaws.com",
            continuation_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            aws_region="us-east-1",
        )

        assert mock_get_paginated_data.call_count == 2
        assert mock_process_page.call_count == 1
        assert result["pages_processed"] == 2
        mock_merge_metrics.assert_called_once()

    @patch("monthly_reports.processing.merge_metrics")
    @patch("monthly_reports.processing.initialize_metrics")
    @patch("monthly_reports.processing.process_accounts_page")
    @patch("monthly_reports.processing.get_paginated_table_data")
    def test_process_accounts_scan_continuation_no_last_evaluated_key(
        self,
        mock_get_paginated_data,
        mock_process_page,
        mock_initialize_metrics,
        mock_merge_metrics,
        mock_logger,
    ):
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 60000

        mock_initialize_metrics.return_value = {"pages_processed": 0}
        mock_get_paginated_data.side_effect = [
            ([{"accountId": "123", "userId": "456"}], None)
        ]
        mock_process_page.return_value = {"processed_count": 1}

        result = process_accounts_scan_continuation(
            scan_params={},
            statement_period="2024-1",
            context=mock_context,
            logger=mock_logger,
            accounts_table=MagicMock(),
            sfn_client=MagicMock(),
            state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:test",
            sqs_endpoint="https://sqs.us-east-1.amazonaws.com",
            continuation_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            aws_region="us-east-1",
        )

        assert mock_get_paginated_data.call_count == 1
        assert mock_process_page.call_count == 1
        assert result["pages_processed"] == 1

        mock_merge_metrics.assert_called_once()

    @patch("monthly_reports.processing.send_continuation_message")
    @patch("monthly_reports.processing.initialize_metrics")
    def test_process_accounts_scan_continuation_timeout(
        self, mock_initialize_metrics, mock_send_continuation, mock_logger
    ):
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 20000  # 20 seconds

        mock_initialize_metrics.return_value = {"pages_processed": 0}

        result = process_accounts_scan_continuation(
            scan_params={},
            statement_period="2024-1",
            context=mock_context,
            logger=mock_logger,
            accounts_table=MagicMock(),
            sfn_client=MagicMock(),
            state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:test",
            sqs_endpoint="https://sqs.us-east-1.amazonaws.com",
            continuation_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            aws_region="us-east-1",
            safety_buffer=30,
        )

        mock_send_continuation.assert_called_once()
        assert result["pages_processed"] == 0

    @patch("monthly_reports.processing.get_paginated_table_data")
    @patch("monthly_reports.processing.initialize_metrics")
    def test_process_accounts_scan_continuation_no_accounts(
        self, mock_initialize_metrics, mock_get_paginated_data, mock_logger
    ):
        mock_context = MagicMock()
        mock_context.get_remaining_time_in_millis.return_value = 60000

        mock_initialize_metrics.return_value = {"pages_processed": 0}
        mock_get_paginated_data.return_value = ([], None)

        result = process_accounts_scan_continuation(
            scan_params={},
            statement_period="2024-1",
            context=mock_context,
            logger=mock_logger,
            accounts_table=MagicMock(),
            sfn_client=MagicMock(),
            state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:test",
            sqs_endpoint="https://sqs.us-east-1.amazonaws.com",
            continuation_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            aws_region="us-east-1",
        )

        assert result["pages_processed"] == 1


class TestProcessBatchContinuation:

    @patch("monthly_reports.processing.process_accounts_scan_continuation")
    @patch("monthly_reports.processing.process_account_batches")
    @patch("monthly_reports.processing.initialize_metrics")
    @patch("monthly_reports.processing.merge_metrics")
    def test_process_batch_continuation_with_remaining_accounts_and_key(
        self,
        mock_merge_metrics,
        mock_initialize_metrics,
        mock_process_batches,
        mock_process_scan,
        mock_logger,
    ):
        mock_initialize_metrics.return_value = {"processed_count": 0}
        mock_process_batches.return_value = {"processed_count": 2}
        mock_process_scan.return_value = {"processed_count": 5}

        remaining_accounts = [
            {"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())},
            {"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())},
        ]

        process_batch_continuation(
            scan_params={},
            statement_period="2024-1",
            remaining_accounts=remaining_accounts,
            last_evaluated_key={"id": "test"},
            context=MagicMock(),
            logger=mock_logger,
            accounts_table=MagicMock(),
            sfn_client=MagicMock(),
            state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:test",
            sqs_endpoint="https://sqs.us-east-1.amazonaws.com",
            continuation_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            aws_region="us-east-1",
        )

        mock_process_batches.assert_called_once()
        mock_process_scan.assert_called_once()
        assert mock_merge_metrics.call_count == 2

    @patch("monthly_reports.processing.process_accounts_scan_continuation")
    @patch("monthly_reports.processing.initialize_metrics")
    @patch("monthly_reports.processing.merge_metrics")
    def test_process_batch_continuation_no_remaining_accounts_with_key(
        self,
        mock_merge_metrics,
        mock_initialize_metrics,
        mock_process_scan,
        mock_logger,
    ):
        mock_initialize_metrics.return_value = {"processed_count": 0}
        mock_process_scan.return_value = {"processed_count": 5}

        process_batch_continuation(
            scan_params={},
            statement_period="2024-1",
            remaining_accounts=[],
            last_evaluated_key={"id": "test"},
            context=MagicMock(),
            logger=mock_logger,
            accounts_table=MagicMock(),
            sfn_client=MagicMock(),
            state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:test",
            sqs_endpoint="https://sqs.us-east-1.amazonaws.com",
            continuation_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            aws_region="us-east-1",
        )

        mock_process_scan.assert_called_once()
        assert mock_merge_metrics.call_count == 1

    @patch("monthly_reports.processing.process_account_batches")
    @patch("monthly_reports.processing.initialize_metrics")
    @patch("monthly_reports.processing.merge_metrics")
    def test_process_batch_continuation_remaining_accounts_no_key(
        self,
        mock_merge_metrics,
        mock_initialize_metrics,
        mock_process_batches,
        mock_logger,
    ):
        mock_initialize_metrics.return_value = {"processed_count": 0}
        mock_process_batches.return_value = {"processed_count": 2}

        remaining_accounts = [
            {"accountId": str(uuid.uuid4()), "userId": str(uuid.uuid4())},
        ]

        process_batch_continuation(
            scan_params={},
            statement_period="2024-1",
            remaining_accounts=remaining_accounts,
            last_evaluated_key=None,
            context=MagicMock(),
            logger=mock_logger,
            accounts_table=MagicMock(),
            sfn_client=MagicMock(),
            state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:test",
            sqs_endpoint="https://sqs.us-east-1.amazonaws.com",
            continuation_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            aws_region="us-east-1",
        )

        mock_process_batches.assert_called_once()
        assert mock_merge_metrics.call_count == 1

    @patch("monthly_reports.processing.initialize_metrics")
    def test_process_batch_continuation_no_remaining_accounts_no_key(
        self, mock_initialize_metrics, mock_logger
    ):
        mock_initialize_metrics.return_value = {"processed_count": 0}

        result = process_batch_continuation(
            scan_params={},
            statement_period="2024-1",
            remaining_accounts=[],
            last_evaluated_key=None,
            context=MagicMock(),
            logger=mock_logger,
            accounts_table=MagicMock(),
            sfn_client=MagicMock(),
            state_machine_arn="arn:aws:states:us-east-1:123456789012:stateMachine:test",
            sqs_endpoint="https://sqs.us-east-1.amazonaws.com",
            continuation_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            aws_region="us-east-1",
        )

        assert result == {"processed_count": 0}
