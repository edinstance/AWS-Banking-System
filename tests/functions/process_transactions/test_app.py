import uuid
from unittest.mock import patch, MagicMock

import pytest

from functions.process_transactions.process_transactions.app import lambda_handler
from functions.process_transactions.process_transactions.exceptions import (
    BusinessLogicError,
    TransactionSystemError,
)


@pytest.fixture
def sample_event_with_records():
    return {
        "Records": [
            {
                "eventName": "INSERT",
                "dynamodb": {
                    "SequenceNumber": "12345",
                    "NewImage": {
                        "id": {"S": str(uuid.uuid4())},
                        "accountId": {"S": str(uuid.uuid4())},
                        "userId": {"S": str(uuid.uuid4())},
                        "idempotencyKey": {"S": str(uuid.uuid4())},
                        "amount": {"N": "100.50"},
                        "type": {"S": "DEPOSIT"},
                    },
                },
            }
        ]
    }


class TestLambdaHandler:

    @patch(
        "functions.process_transactions.process_transactions.app.accounts_table", None
    )
    @patch(
        "functions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    def test_accounts_table_not_initialized(self, mock_context, environment_variables):
        event = {"Records": []}

        with pytest.raises(TransactionSystemError) as exc_info:
            lambda_handler(event, mock_context)

        assert str(exc_info.value) == "DynamoDB table not initialized"

    @patch(
        "functions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.transactions_table",
        None,
    )
    def test_transactions_table_not_initialized(
        self, mock_context, environment_variables
    ):
        event = {"Records": []}

        with pytest.raises(TransactionSystemError) as exc_info:
            lambda_handler(event, mock_context)

        assert str(exc_info.value) == "Transactions table not initialized"

    def test_table_initialization_with_environment_variables(
        self, process_app_with_mocked_tables
    ):
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
        "functions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    def test_no_records(self, mock_context, environment_variables):
        event = {"Records": []}

        result = lambda_handler(event, mock_context)

        assert result == {"statusCode": 200, "message": "No records to process"}

    @patch(
        "functions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    def test_no_insert_records(self, mock_context, environment_variables):
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
        "functions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.process_single_transaction"
    )
    def test_successful_processing(
        self,
        mock_process_single_transaction,
        mock_context,
        sample_event_with_records,
        environment_variables,
    ):
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
        "functions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.process_transactions.process_transactions.app.update_transaction_status"
    )
    def test_business_logic_error_with_idempotency_key(
        self,
        mock_update_transaction_status,
        mock_process_single_transaction,
        mock_context,
        sample_event_with_records,
        environment_variables,
    ):
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
        "functions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.process_transactions.process_transactions.app.send_dynamodb_record_to_dlq"
    )
    def test_business_logic_error_without_idempotency_key(
        self,
        mock_send_to_dlq,
        mock_process_single_transaction,
        mock_context,
        environment_variables,
    ):
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
        "functions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.process_transactions.process_transactions.app.send_dynamodb_record_to_dlq",
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
        "functions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.process_transactions.process_transactions.app.update_transaction_status"
    )
    @patch(
        "functions.process_transactions.process_transactions.app.send_dynamodb_record_to_dlq"
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
        "functions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.process_transactions.process_transactions.app.update_transaction_status"
    )
    @patch(
        "functions.process_transactions.process_transactions.app.send_dynamodb_record_to_dlq"
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
        "functions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.process_transactions.process_transactions.app.send_dynamodb_record_to_dlq"
    )
    def test_transaction_system_error(
        self,
        mock_send_to_dlq,
        mock_process_single_transaction,
        mock_context,
        sample_event_with_records,
        environment_variables,
    ):
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
        "functions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.process_transactions.process_transactions.app.send_dynamodb_record_to_dlq"
    )
    def test_transaction_system_error_and_dlq_fails(
        self,
        mock_send_to_dlq,
        mock_process_single_transaction,
        mock_context,
        sample_event_with_records,
        environment_variables,
    ):
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
        "functions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.process_transactions.process_transactions.app.send_dynamodb_record_to_dlq"
    )
    def test_lambda_handler_generic_exception(
        self,
        mock_send_to_dlq,
        mock_process_single_transaction,
        mock_context,
        sample_event_with_records,
        environment_variables,
    ):
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
        "functions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.process_transactions.process_transactions.app.send_dynamodb_record_to_dlq"
    )
    def test_generic_exception_and_dlq_fails(
        self,
        mock_send_to_dlq,
        mock_process_single_transaction,
        mock_context,
        sample_event_with_records,
        environment_variables,
    ):
        mock_process_single_transaction.side_effect = Exception("Unexpected error")
        mock_send_to_dlq.return_value = False

        with pytest.raises(TransactionSystemError) as exc_info:
            lambda_handler(sample_event_with_records, mock_context)

        assert (
            "Critical failure: 1 records could not be processed or sent to DLQ"
            in str(exc_info.value)
        )

    @patch(
        "functions.process_transactions.process_transactions.app.accounts_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.transactions_table",
        MagicMock(),
    )
    @patch(
        "functions.process_transactions.process_transactions.app.process_single_transaction"
    )
    @patch(
        "functions.process_transactions.process_transactions.app.update_transaction_status"
    )
    @patch(
        "functions.process_transactions.process_transactions.app.send_dynamodb_record_to_dlq"
    )
    def test_lambda_handler_success_and_failure(
        self,
        mock_send_to_dlq,
        mock_update_transaction_status,
        mock_process_single_transaction,
        mock_context,
        environment_variables,
    ):
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
