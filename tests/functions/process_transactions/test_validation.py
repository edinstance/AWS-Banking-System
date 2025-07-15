import uuid
from decimal import Decimal

import pytest

from functions.process_transactions.process_transactions.exceptions import (
    TransactionProcessingError,
)
from functions.process_transactions.process_transactions.validation import (
    validate_transaction_data,
)


@pytest.fixture
def valid_event():
    """
    Return a sample valid transaction event dictionary formatted with DynamoDB-style type annotations.

    The returned dictionary includes fields for account ID, user ID, transaction ID, idempotency key, transaction type, and amount, each with appropriate type wrappers.
    """
    return {
        "accountId": {"S": str(uuid.uuid4())},
        "userId": {"S": str(uuid.uuid4())},
        "id": {"S": str(uuid.uuid4())},
        "idempotencyKey": {"S": str(uuid.uuid4())},
        "type": {"S": "DEPOSIT"},
        "amount": {"N": "100"},
    }


class TestValidation:
    def test_missing_fields(self, mock_logger):
        """
        Test that validation fails with a specific error when all required transaction fields are missing.
        """
        with pytest.raises(TransactionProcessingError) as exception_info:
            validate_transaction_data({}, mock_logger)

        assert exception_info.type is TransactionProcessingError
        assert (
            str(exception_info.value)
            == "Missing required fields: ['accountId', 'amount', 'type', 'userId', 'id', 'idempotencyKey']"
        )

    def test_invalid_transaction_type(self, mock_logger, valid_event):
        """
        Test that an invalid transaction type in the event data raises a TransactionProcessingError with the expected message.
        """
        event_with_invalid_type = valid_event.copy()
        event_with_invalid_type["type"]["S"] = "INVALID"

        with pytest.raises(TransactionProcessingError) as exception_info:
            validate_transaction_data(event_with_invalid_type, mock_logger)

        assert exception_info.type is TransactionProcessingError
        assert str(exception_info.value) == "Invalid transaction type: INVALID"

    def test_negative_amount(self, mock_logger, valid_event):
        """
        Test that a negative transaction amount raises a TransactionProcessingError with the correct message.
        """
        event_with_invalid_amount = valid_event.copy()
        event_with_invalid_amount["amount"]["N"] = "-1"

        with pytest.raises(TransactionProcessingError) as exception_info:
            validate_transaction_data(event_with_invalid_amount, mock_logger)

        assert exception_info.type is TransactionProcessingError
        assert str(exception_info.value) == "Amount must be positive: -1"

    def test_success(self, mock_logger, valid_event):
        """
        Test that valid transaction event data is correctly validated and mapped to the expected output fields.
        """
        result = validate_transaction_data(valid_event, mock_logger)

        assert result["account_id"] == valid_event["accountId"]["S"]
        assert result["user_id"] == valid_event["userId"]["S"]
        assert result["idempotency_key"] == valid_event["idempotencyKey"]["S"]
        assert result["transaction_type"] == valid_event["type"]["S"]
        assert result["transaction_id"] == valid_event["id"]["S"]
        assert result["amount"] == Decimal(valid_event["amount"]["N"])

    def test_exception(self, mock_logger, valid_event):
        """
        Test that a transaction event missing the transaction type value raises a TransactionProcessingError with an invalid record format message.
        """
        event_with_invalid_type = valid_event.copy()
        del event_with_invalid_type["type"]["S"]

        with pytest.raises(TransactionProcessingError) as exception_info:
            validate_transaction_data(event_with_invalid_type, mock_logger)

        assert exception_info.type is TransactionProcessingError
        assert "Invalid record format: " in str(exception_info.value)
