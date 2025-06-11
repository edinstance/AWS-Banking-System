from datetime import datetime, timezone
from decimal import Decimal

import pytest
from botocore.exceptions import ClientError

from functions.record_transactions.record_transactions.transactions import (
    validate_transaction_data,
    check_existing_transaction,
    save_transaction,
)
from tests.record_transaction_tests.conftest import VALID_TRANSACTION_TYPES, VALID_UUID


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
        with pytest.raises(Exception) as exc_info:
            check_existing_transaction("test-key", None, mock_logger)
        assert "Database not configured" in str(exc_info.value)
        mock_logger.error.assert_called_once()

    def test_no_existing_transaction(self, mock_table, mock_logger):
        mock_table.query.return_value = {"Items": []}
        result = check_existing_transaction("test-key", mock_table, mock_logger)
        assert result is None

    def test_existing_valid_transaction(self, mock_table, mock_logger):
        future_timestamp = int(datetime.now(timezone.utc).timestamp()) + 3600
        mock_item = {"id": "test-id", "idempotencyExpiration": future_timestamp}
        mock_table.query.return_value = {"Items": [mock_item]}

        result = check_existing_transaction("test-key", mock_table, mock_logger)
        assert result == mock_item

    def test_expired_transaction(self, mock_table, mock_logger):
        past_timestamp = int(datetime.now(timezone.utc).timestamp()) - 3600
        mock_item = {"id": "test-id", "idempotencyExpiration": past_timestamp}
        mock_table.query.return_value = {"Items": [mock_item]}

        result = check_existing_transaction("test-key", mock_table, mock_logger)
        assert result is None

    def test_throughput_exceeded(self, mock_table, mock_logger):
        error_response = {
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": "Rate exceeded",
            }
        }
        mock_table.query.side_effect = ClientError(error_response, "Query")

        with pytest.raises(Exception) as exc_info:
            check_existing_transaction("test-key", mock_table, mock_logger)
        assert "Service temporarily unavailable" in str(exc_info.value)

    def test_unknown_error(self, mock_table, mock_logger):
        error_response = {
            "Error": {
                "Code": "UnknownError",
                "Message": "Rate exceeded",
            }
        }
        mock_table.query.side_effect = ClientError(error_response, "Query")

        with pytest.raises(Exception) as exc_info:
            check_existing_transaction("test-key", mock_table, mock_logger)
        assert "UnknownError" in str(exc_info.value)


class TestSaveTransaction:
    def test_no_table_configured(self, mock_logger):
        with pytest.raises(Exception) as exc_info:
            save_transaction({}, None, mock_logger)
        assert "Database not configured" in str(exc_info.value)
        mock_logger.error.assert_called_once()

    def test_successful_save(self, mock_table, mock_logger):
        transaction_item = {"id": "test-id", "amount": Decimal("100.50")}
        result = save_transaction(transaction_item, mock_table, mock_logger)
        assert result is True

    def test_throughput_exceeded_on_save(self, mock_table, mock_logger):
        error_response = {
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": "Rate exceeded",
            }
        }
        mock_table.put_item.side_effect = ClientError(error_response, "PutItem")

        with pytest.raises(Exception) as exc_info:
            save_transaction({}, mock_table, mock_logger)
        assert "Service temporarily unavailable" in str(exc_info.value)

    def test_resource_not_found_on_save(self, mock_table, mock_logger):
        error_response = {
            "Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}
        }
        mock_table.put_item.side_effect = ClientError(error_response, "PutItem")

        with pytest.raises(Exception) as exc_info:
            save_transaction({}, mock_table, mock_logger)
        assert "Transaction database configuration error" in str(exc_info.value)

    def test_other_client_error_on_save(self, mock_table, mock_logger):
        error_response = {
            "Error": {"Code": "UnknownError", "Message": "Unknown error occurred"}
        }
        mock_table.put_item.side_effect = ClientError(error_response, "PutItem")

        with pytest.raises(Exception) as exc_info:
            save_transaction({}, mock_table, mock_logger)
        assert "Database error: UnknownError" in str(exc_info.value)

    def test_conditional_error(self, mock_table, mock_logger):
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
