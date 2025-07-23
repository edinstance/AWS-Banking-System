import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from botocore.exceptions import ClientError

from functions.transactions.request_transaction.request_transaction.transactions import (
    validate_transaction_data,
    check_existing_transaction,
    save_transaction,
    build_transaction_item,
)
from tests.functions.transactions.request_transaction.conftest import (
    VALID_TRANSACTION_TYPES,
    VALID_UUID,
)


class TestValidateTransactionData:
    def test_valid_transaction_data(self, valid_transaction_data):
        is_valid, error = validate_transaction_data(
            valid_transaction_data, VALID_TRANSACTION_TYPES
        )
        assert is_valid is True
        assert error is None

    def test_missing_required_field(self):
        data = {"accountId": VALID_UUID, "amount": "100.50"}
        is_valid, error = validate_transaction_data(data, VALID_TRANSACTION_TYPES)
        assert is_valid is False
        assert "Missing required fields: type" in error

    def test_invalid_transaction_type(self, valid_transaction_data):
        """
        Tests that an invalid transaction type causes validation to fail with an appropriate error message.
        """
        data = valid_transaction_data.copy()
        data["type"] = "INVALID_TYPE"
        is_valid, error = validate_transaction_data(data, VALID_TRANSACTION_TYPES)
        assert is_valid is False
        assert "Invalid transaction type" in error

    def test_invalid_amount_format(self, valid_transaction_data):
        data = valid_transaction_data.copy()
        data["amount"] = "not_a_number"
        is_valid, error = validate_transaction_data(data, VALID_TRANSACTION_TYPES)
        assert is_valid is False
        assert "Invalid amount format" in error

    def test_negative_amount(self, valid_transaction_data):
        """
        Tests that a negative transaction amount is rejected by the validation function.

        Verifies that providing a negative amount results in validation failure and the appropriate error message.
        """
        data = valid_transaction_data.copy()
        data["amount"] = "-100.50"
        is_valid, error = validate_transaction_data(data, VALID_TRANSACTION_TYPES)
        assert is_valid is False
        assert "Amount must be a positive number" in error

    def test_invalid_account_id(self, valid_transaction_data):
        data = valid_transaction_data.copy()
        data["accountId"] = "not-a-uuid"
        is_valid, error = validate_transaction_data(data, VALID_TRANSACTION_TYPES)
        assert is_valid is False
        assert "Invalid accountId" in error

    def test_invalid_description_type(self, valid_transaction_data):
        data = valid_transaction_data.copy()
        data["description"] = 123
        is_valid, error = validate_transaction_data(data, VALID_TRANSACTION_TYPES)
        assert is_valid is False
        assert "Description must be a string" in error


class TestCheckExistingTransaction:
    def test_no_table_configured(self, mock_logger):
        """
        Test that an exception is raised when no database table is provided to check for an existing transaction.
        """
        with pytest.raises(Exception) as exc_info:
            check_existing_transaction("test-key", None, mock_logger)
        assert "Database not configured" in str(exc_info.value)
        mock_logger.error.assert_called_once()

    def test_no_existing_transaction(self, mock_table, mock_logger):
        """
        Test that `check_existing_transaction` returns None when no transaction exists for the given idempotency key.
        """
        mock_table.get_item.return_value = {"Item": None}
        result = check_existing_transaction("test-key", mock_table, mock_logger)
        assert result is None

    def test_existing_valid_transaction(self, mock_table, mock_logger):
        """
        Tests that an existing transaction with a valid, unexpired idempotency key is returned.

        Verifies that when a transaction with a future idempotency expiration is found in the database, the function returns the transaction item.
        """
        future_timestamp = int(datetime.now(timezone.utc).timestamp()) + 3600
        mock_item = {"id": "test-id", "idempotencyExpiration": future_timestamp}
        mock_table.get_item.return_value = {"Item": mock_item}

        result = check_existing_transaction("test-key", mock_table, mock_logger)
        assert result == mock_item

    def test_throughput_exceeded(self, mock_table, mock_logger):
        """
        Verify that a throughput exceeded error during transaction lookup raises a ClientError with the correct error code.

        Simulates a DynamoDB ProvisionedThroughputExceededException when retrieving a transaction and asserts that the resulting exception contains the expected error code.
        """
        error_response = {
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": "Rate exceeded",
            }
        }
        mock_table.get_item.side_effect = ClientError(error_response, "GetItem")

        with pytest.raises(ClientError) as exc_info:
            check_existing_transaction("test-key", mock_table, mock_logger)
        assert "ProvisionedThroughputExceededException" in str(exc_info.value)

    def test_unknown_error(self, mock_table, mock_logger):
        """
        Test that an unknown client error during transaction lookup raises a ClientError with the correct error code in the exception message.
        """
        error_response = {
            "Error": {
                "Code": "UnknownError",
                "Message": "Rate exceeded",
            }
        }
        mock_table.get_item.side_effect = ClientError(error_response, "GetItem")

        with pytest.raises(ClientError) as exc_info:
            check_existing_transaction("test-key", mock_table, mock_logger)
        assert "UnknownError" in str(exc_info.value)


class TestSaveTransaction:
    def test_no_table_configured(self, mock_logger):
        with pytest.raises(Exception) as exc_info:
            save_transaction({}, None, mock_logger)
        assert "Database not configured" in str(exc_info.value)
        mock_logger.error.assert_called_once()

    def test_successful_save(self, mock_table, mock_logger):
        """
        Tests that save_transaction returns True when the transaction item is successfully saved.
        """
        transaction_item = {"id": "test-id", "amount": Decimal("100.50")}
        result = save_transaction(transaction_item, mock_table, mock_logger)
        assert result is True

    def test_throughput_exceeded_on_save(self, mock_table, mock_logger):
        """
        Tests that save_transaction raises an exception with a service unavailable message when a throughput exceeded error occurs during save.
        """
        error_response = {
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": "Rate exceeded",
            }
        }
        mock_table.put_item.side_effect = ClientError(error_response, "PutItem")

        with pytest.raises(ClientError) as exc_info:
            save_transaction({}, mock_table, mock_logger)
        assert "ProvisionedThroughputExceededException" in str(exc_info.value)

    def test_resource_not_found_on_save(self, mock_table, mock_logger):
        """
        Test that saving a transaction raises a ClientError with a 'ResourceNotFoundException' when the database table does not exist.
        """
        error_response = {
            "Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}
        }
        mock_table.put_item.side_effect = ClientError(error_response, "PutItem")

        with pytest.raises(ClientError) as exc_info:
            save_transaction({}, mock_table, mock_logger)
        assert "ResourceNotFoundException" in str(exc_info.value)

    def test_other_client_error_on_save(self, mock_table, mock_logger):
        """
        Test that save_transaction raises a ClientError with the correct error code when an unknown client error occurs during the save operation.
        """
        error_response = {
            "Error": {"Code": "UnknownError", "Message": "Unknown error occurred"}
        }
        mock_table.put_item.side_effect = ClientError(error_response, "PutItem")

        with pytest.raises(ClientError) as exc_info:
            save_transaction({}, mock_table, mock_logger)
        assert "UnknownError" in str(exc_info.value)

    def test_conditional_error(self, mock_table, mock_logger):
        """
        Tests that save_transaction raises an exception when a conditional check fails due to idempotency expiration.

        Simulates a ConditionalCheckFailedException from the database and asserts that the correct exception is raised.
        """
        error_response = {
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "IdempotencyExpiration",
            }
        }
        mock_table.put_item.side_effect = ClientError(error_response, "PutItem")

        with pytest.raises(Exception) as exc_info:
            save_transaction({}, mock_table, mock_logger)

        assert (
            "An error occurred (ConditionalCheckFailedException) when calling the PutItem operation"
            in str(exc_info.value)
        )


class TestBuildTransaction:
    def test_successful_item_creation(self):
        """
        Tests that build_transaction_item returns a dictionary containing the expected transaction ID and idempotency key fields.
        """
        transaction_id = str(uuid.uuid4())
        request_body = {
            "accountId": str(uuid.uuid4()),
            "type": "deposit",
            "description": "Monthly savings",
            "amount": 100.50,
        }
        user_id = str(uuid.uuid4())
        idempotency_key = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        result = build_transaction_item(
            transaction_id,
            request_body,
            user_id,
            idempotency_key,
            request_id,
        )

        assert result is not None
        assert result["id"] == transaction_id
        assert result["idempotencyKey"] == idempotency_key
