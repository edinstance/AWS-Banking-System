import uuid
from unittest.mock import patch, MagicMock

import pytest

from functions.transactions.process_transactions.process_transactions.app import (
    lambda_handler,
)
from functions.transactions.process_transactions.process_transactions.exceptions import (
    BusinessLogicError,
    TransactionSystemError,
)


class TestLambdaHandler:

    @patch(
        "functions.transactions.process_transactions.process_transactions.app.accounts_table",
        None,
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    def test_accounts_table_not_initialized(self, mock_context, environment_variables):
        """
        Test that lambda_handler raises TransactionSystemError when the accounts table is not initialised.
        """
        event = {"Records": []}

        with pytest.raises(TransactionSystemError) as exc_info:
            lambda_handler(event, mock_context)

        assert str(exc_info.value) == "DynamoDB table not initialized"

    @patch(
        "functions.transactions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.transactions_table",
        None,
    )
    def test_transactions_table_not_initialized(
        self, mock_context, environment_variables
    ):
        """
        Test that the lambda_handler raises a TransactionSystemError when the transactions table is not initialised.
        """
        event = {"Records": []}

        with pytest.raises(TransactionSystemError) as exc_info:
            lambda_handler(event, mock_context)

        assert str(exc_info.value) == "Transactions table not initialized"

    def test_table_initialization_with_environment_variables(
        self, process_app_with_mocked_tables
    ):
        """
        Verify that the transactions and accounts tables are initialised using the expected environment variable table names.
        """
        assert process_app_with_mocked_tables.transactions_table is not None
        assert process_app_with_mocked_tables.accounts_table is not None

        assert (
            process_app_with_mocked_tables.TRANSACTIONS_TABLE_NAME
            == "test-transactions-table"
        )
        assert (
            process_app_with_mocked_tables.ACCOUNTS_TABLE_NAME == "test-accounts-table"
        )

    @patch(
        "functions.transactions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    def test_no_records(self, mock_context, environment_variables):
        """
        Test that the lambda_handler returns a 200 response with an appropriate message when the event contains no records.
        """
        event = {"Records": []}

        result = lambda_handler(event, mock_context)

        assert result == {"statusCode": 200, "message": "No records to process"}

    @patch(
        "functions.transactions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    def test_no_insert_records(self, mock_context, environment_variables):
        """
        Test that the lambda_handler returns a 200 response with an appropriate message when no INSERT records are present in the event.
        """
        event = {
            "Records": [
                {
                    "eventName": "MODIFY",
                    "dynamodb": {
                        "SequenceNumber": "12345",
                        "NewImage": {
                            "id": {"S": str(uuid.uuid4())},
                            "accountId": {"S": str(uuid.uuid4())},
                        },
                    },
                }
            ]
        }

        result = lambda_handler(event, mock_context)

        assert result == {"statusCode": 200, "message": "No INSERT records to process"}

    @patch(
        "functions.transactions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.process_single_transaction"
    )
    def test_successful_processing(
        self,
        mock_process_single_transaction,
        mock_context,
        sample_event_with_records,
        environment_variables,
    ):
        """
        Test that the lambda_handler processes a single valid INSERT record successfully.

        Verifies that the handler returns a 200 status code with correct counts when processing succeeds, and that process_single_transaction is called once.
        """
        mock_process_single_transaction.return_value = None

        result = lambda_handler(sample_event_with_records, mock_context)

        assert result == {
            "statusCode": 200,
            "processedRecords": 1,
            "successful": 1,
            "businessLogicFailures": 0,
            "systemFailures": 0,
        }
        mock_process_single_transaction.assert_called_once()

    @patch(
        "functions.transactions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.update_transaction_status"
    )
    def test_business_logic_error_with_idempotency_key(
        self,
        mock_update_transaction_status,
        mock_process_single_transaction,
        mock_context,
        sample_event_with_records,
        environment_variables,
    ):
        """
        Test that the lambda_handler correctly handles a BusinessLogicError when an idempotency key is present in the transaction record.

        Verifies that the transaction status is updated and the response indicates a business logic failure with no successful or system failures.
        """
        mock_process_single_transaction.side_effect = BusinessLogicError(
            "Test business logic error"
        )
        mock_update_transaction_status.return_value = None

        result = lambda_handler(sample_event_with_records, mock_context)

        assert result == {
            "statusCode": 200,
            "processedRecords": 1,
            "successful": 0,
            "businessLogicFailures": 1,
            "systemFailures": 0,
        }
        mock_update_transaction_status.assert_called_once()

    @patch(
        "functions.transactions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.send_message_to_sqs"
    )
    def test_business_logic_error_without_idempotency_key(
        self,
        mock_send_to_dlq,
        mock_process_single_transaction,
        mock_context,
        environment_variables,
    ):
        """
        Test that a business logic error without an idempotency key results in the record being sent to the DLQ.

        Simulates an INSERT event where `process_single_transaction` raises a `BusinessLogicError` and the record lacks an idempotency key. Verifies that the handler sends the record to the dead-letter queue and returns a response indicating one business logic failure.
        """
        event = {
            "Records": [
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "SequenceNumber": "12345",
                        "NewImage": {
                            "id": {"S": str(uuid.uuid4())},
                            "accountId": {"S": str(uuid.uuid4())},
                        },
                    },
                }
            ]
        }

        mock_process_single_transaction.side_effect = BusinessLogicError(
            "Test business logic error"
        )
        mock_send_to_dlq.return_value = True

        result = lambda_handler(event, mock_context)

        assert result == {
            "statusCode": 200,
            "processedRecords": 1,
            "successful": 0,
            "businessLogicFailures": 1,
            "systemFailures": 0,
        }
        mock_send_to_dlq.assert_called_once()

    @patch(
        "functions.transactions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.send_message_to_sqs",
        return_value=False,
    )
    def test_error_without_idempotency_key_and_dlq_fails(
        self,
        mock_send_to_dlq,
        mock_process_single_transaction,
        mock_context,
        environment_variables,
        sample_event_with_records,
    ):
        """
        Test that a TransactionSystemError is raised when a business logic error occurs, the record lacks an idempotency key, and sending to the DLQ fails.

        This verifies that the lambda_handler raises a critical failure if it cannot process a record or send it to the dead-letter queue.
        """
        mock_process_single_transaction.side_effect = BusinessLogicError(
            "Test business logic error"
        )

        event = sample_event_with_records
        del event["Records"][0]["dynamodb"]["NewImage"]["idempotencyKey"]

        with pytest.raises(TransactionSystemError) as exc_info:
            lambda_handler(event, mock_context)

        assert (
            "Critical failure: 1 records could not be processed or sent to DLQ"
            in str(exc_info.value)
        )
        mock_send_to_dlq.assert_called_once()

    @patch(
        "functions.transactions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.update_transaction_status"
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.send_message_to_sqs"
    )
    def test_business_logic_error_and_update_status_fails(
        self,
        mock_send_to_dlq,
        mock_update_transaction_status,
        mock_process_single_transaction,
        mock_context,
        sample_event_with_records,
        environment_variables,
    ):
        """
        Test that when a business logic error occurs and updating transaction status fails, the record is sent to the DLQ and the handler monthly_reports a business logic failure.

        Simulates `process_single_transaction` raising a `BusinessLogicError`, `update_transaction_status` raising an exception, and `send_message_to_sqs` succeeding. Verifies the handler returns a 200 response with one business logic failure and that the DLQ function is called once.
        """
        mock_process_single_transaction.side_effect = BusinessLogicError(
            "Test business logic error"
        )
        mock_update_transaction_status.side_effect = Exception("Update status failed")
        mock_send_to_dlq.return_value = True

        result = lambda_handler(sample_event_with_records, mock_context)

        assert result == {
            "statusCode": 200,
            "processedRecords": 1,
            "successful": 0,
            "businessLogicFailures": 1,
            "systemFailures": 0,
        }
        mock_send_to_dlq.assert_called_once()

    @patch(
        "functions.transactions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.update_transaction_status"
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.send_message_to_sqs"
    )
    def test_business_logic_error_and_dlq_fails(
        self,
        mock_send_to_dlq,
        mock_update_transaction_status,
        mock_process_single_transaction,
        mock_context,
        sample_event_with_records,
        environment_variables,
    ):
        """
        Test that a TransactionSystemError is raised when both updating transaction status and sending to DLQ fail after a BusinessLogicError.

        Simulates a business logic error during transaction processing, with both status update and DLQ operations failing, and verifies that a critical system error is raised.
        """
        mock_process_single_transaction.side_effect = BusinessLogicError(
            "Test business logic error"
        )
        mock_update_transaction_status.side_effect = Exception("Update status failed")
        mock_send_to_dlq.return_value = False

        with pytest.raises(TransactionSystemError) as exc_info:
            lambda_handler(sample_event_with_records, mock_context)

        assert (
            "Critical failure: 1 records could not be processed or sent to DLQ"
            in str(exc_info.value)
        )

    @patch(
        "functions.transactions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.send_message_to_sqs"
    )
    def test_transaction_system_error(
        self,
        mock_send_to_dlq,
        mock_process_single_transaction,
        mock_context,
        sample_event_with_records,
        environment_variables,
    ):
        """
        Test that the lambda_handler correctly handles a TransactionSystemError by sending the record to the DLQ and reporting a system failure in the response.
        """
        mock_process_single_transaction.side_effect = TransactionSystemError(
            "Test system error"
        )
        mock_send_to_dlq.return_value = True

        result = lambda_handler(sample_event_with_records, mock_context)

        assert result == {
            "statusCode": 200,
            "processedRecords": 1,
            "successful": 0,
            "businessLogicFailures": 0,
            "systemFailures": 1,
        }
        mock_send_to_dlq.assert_called_once()

    @patch(
        "functions.transactions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.send_message_to_sqs"
    )
    def test_transaction_system_error_and_dlq_fails(
        self,
        mock_send_to_dlq,
        mock_process_single_transaction,
        mock_context,
        sample_event_with_records,
        environment_variables,
    ):
        """
        Test that a TransactionSystemError is raised when both transaction processing and sending to the DLQ fail.

        Simulates a system error during transaction processing and a failure to send the record to the dead-letter queue, verifying that the lambda handler raises a critical TransactionSystemError.
        """
        mock_process_single_transaction.side_effect = TransactionSystemError(
            "Test system error"
        )
        mock_send_to_dlq.return_value = False

        with pytest.raises(TransactionSystemError) as exc_info:
            lambda_handler(sample_event_with_records, mock_context)

        assert (
            "Critical failure: 1 records could not be processed or sent to DLQ"
            in str(exc_info.value)
        )

    @patch(
        "functions.transactions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.send_message_to_sqs"
    )
    def test_lambda_handler_generic_exception(
        self,
        mock_send_to_dlq,
        mock_process_single_transaction,
        mock_context,
        sample_event_with_records,
        environment_variables,
    ):
        """
        Test that the lambda_handler correctly handles a generic exception during transaction processing.

        Simulates a scenario where process_single_transaction raises an unexpected exception, and verifies that the record is sent to the DLQ and the response indicates a system failure.
        """
        mock_process_single_transaction.side_effect = Exception("Unexpected error")
        mock_send_to_dlq.return_value = True

        result = lambda_handler(sample_event_with_records, mock_context)

        assert result == {
            "statusCode": 200,
            "processedRecords": 1,
            "successful": 0,
            "businessLogicFailures": 0,
            "systemFailures": 1,
        }
        mock_send_to_dlq.assert_called_once()

    @patch(
        "functions.transactions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.send_message_to_sqs"
    )
    def test_generic_exception_and_dlq_fails(
        self,
        mock_send_to_dlq,
        mock_process_single_transaction,
        mock_context,
        sample_event_with_records,
        environment_variables,
    ):
        """
        Test that a generic exception during transaction processing and a failed DLQ send results in a critical system error.

        Simulates a scenario where `process_single_transaction` raises a generic exception and sending the record to the dead-letter queue (DLQ) also fails. Expects the `lambda_handler` to raise a `TransactionSystemError` indicating a critical failure.
        """
        mock_process_single_transaction.side_effect = Exception("Unexpected error")
        mock_send_to_dlq.return_value = False

        with pytest.raises(TransactionSystemError) as exc_info:
            lambda_handler(sample_event_with_records, mock_context)

        assert (
            "Critical failure: 1 records could not be processed or sent to DLQ"
            in str(exc_info.value)
        )

    @patch(
        "functions.transactions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.update_transaction_status"
    )
    @patch(
        "functions.transactions.process_transactions.process_transactions.app.send_message_to_sqs"
    )
    def test_lambda_handler_success_and_failure(
        self,
        mock_send_to_dlq,
        mock_update_transaction_status,
        mock_process_single_transaction,
        mock_context,
        environment_variables,
    ):
        """
        Test that the lambda_handler correctly processes multiple records with mixed outcomes.

        Simulates three INSERT records: one processed successfully, one raising a BusinessLogicError, and one raising a TransactionSystemError. Verifies that the handler aggregates results, updates transaction status or sends to DLQ as appropriate, and returns the correct summary in the response.
        """
        event = {
            "Records": [
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "SequenceNumber": "12345",
                        "NewImage": {
                            "id": {"S": str(uuid.uuid4())},
                            "accountId": {"S": str(uuid.uuid4())},
                            "idempotencyKey": {"S": str(uuid.uuid4())},
                        },
                    },
                },
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "SequenceNumber": "67890",
                        "NewImage": {
                            "id": {"S": str(uuid.uuid4())},
                            "accountId": {"S": str(uuid.uuid4())},
                            "idempotencyKey": {"S": str(uuid.uuid4())},
                        },
                    },
                },
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "SequenceNumber": "54321",
                        "NewImage": {
                            "id": {"S": str(uuid.uuid4())},
                            "accountId": {"S": str(uuid.uuid4())},
                            "idempotencyKey": {"S": str(uuid.uuid4())},
                        },
                    },
                },
            ]
        }

        mock_process_single_transaction.side_effect = [
            None,
            BusinessLogicError("Business logic error"),
            TransactionSystemError("System error"),
        ]
        mock_update_transaction_status.return_value = None
        mock_send_to_dlq.return_value = True

        result = lambda_handler(event, mock_context)

        assert result == {
            "statusCode": 200,
            "processedRecords": 3,
            "successful": 1,
            "businessLogicFailures": 1,
            "systemFailures": 1,
        }
        assert mock_process_single_transaction.call_count == 3
        assert mock_update_transaction_status.call_count == 1
        assert mock_send_to_dlq.call_count == 1
