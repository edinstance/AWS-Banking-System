import uuid
from decimal import Decimal

from functions.record_transactions.app import (
    is_valid_uuid,
    validate_transaction_data,
    VALID_TRANSACTION_TYPES,
)


class TestIsValidUUID:
    def test_valid_uuid_v4(self):
        """Test that a valid UUID v4 string returns True."""
        # Generate a real UUID v4
        valid_uuid = str(str(uuid.uuid4()))
        assert is_valid_uuid(valid_uuid) is True

    def test_valid_uuid_uppercase(self):
        """Test that a valid UUID in uppercase still works."""
        valid_uuid = str(str(uuid.uuid4())).upper()
        assert is_valid_uuid(valid_uuid) is True

    def test_invalid_uuid_format(self):
        """
        Tests that is_valid_uuid returns False for an improperly formatted UUID string.
        """
        invalid_uuid = "not-a-uuid"
        assert is_valid_uuid(invalid_uuid) is False

    def test_uuid_wrong_length(self):
        """Test that a string of the wrong length returns False."""
        too_short = "123e4567-e89b-12d3-a456"  # Incomplete UUID
        assert is_valid_uuid(too_short) is False

    def test_uuid_with_invalid_characters(self):
        """
        Tests that a UUID string containing invalid characters is correctly identified as invalid.
        """
        invalid_chars = "123e4567-e89b-12d3-a456-42661417400G"  # 'G' is not hex
        assert is_valid_uuid(invalid_chars) is False

    def test_none_value(self):
        """Test that None returns False."""
        assert is_valid_uuid(None) is False

    def test_empty_string(self):
        """Test that an empty string returns False."""
        assert is_valid_uuid("") is False

    def test_numeric_input(self):
        """
        Tests that passing a numeric input to is_valid_uuid returns False.
        """
        assert is_valid_uuid(12345) is False


class TestValidateTransactionData:
    def test_valid_deposit_transaction(self):
        """Test a valid DEPOSIT transaction passes validation."""
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": 100.50,
            "type": "DEPOSIT",
            "description": "Test deposit",
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

    def test_valid_withdrawal_transaction(self):
        """Test a valid WITHDRAWAL transaction passes validation."""
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": 50.25,
            "type": "WITHDRAWAL",
            "description": "Test withdrawal",
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

    def test_missing_required_fields(self):
        """Test that missing required fields are detected."""
        data = {"amount": 100, "type": "DEPOSIT"}
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Missing required fields" in error
        assert "accountId" in error

        data = {"type": "DEPOSIT"}
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "accountId" in error
        assert "amount" in error

    def test_invalid_transaction_type(self):
        """Test that invalid transaction types are rejected."""
        data = {"accountId": str(uuid.uuid4()), "amount": 100, "type": "INVALID_TYPE"}
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Invalid transaction type" in error

        for valid_type in VALID_TRANSACTION_TYPES:
            assert valid_type in error

    def test_invalid_amount_format(self):
        """
        Tests that the validation rejects transactions with a non-numeric amount field.
        """
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": "not-a-number",
            "type": "DEPOSIT",
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Invalid amount format" in error

    def test_negative_amount(self):
        """Test that negative amounts are rejected for all transaction types."""
        data = {"accountId": str(uuid.uuid4()), "amount": -100, "type": "DEPOSIT"}
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Amount must be a positive number" in error

        data["type"] = "WITHDRAWAL"
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Amount must be a positive number" in error

    def test_zero_amount(self):
        """Test that zero amounts are rejected."""
        data = {"accountId": str(uuid.uuid4()), "amount": 0, "type": "DEPOSIT"}
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Amount must be a positive number" in error

    def test_invalid_account_id(self):
        """
        Tests that transactions with invalid account IDs are correctly rejected.

        Verifies that account IDs which are too short or not strings cause validation to fail,
        and that the appropriate error message is returned.
        """
        data = {"accountId": "abs121", "amount": 100, "type": "DEPOSIT"}
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Invalid accountId, accountId must be a valid UUID" in error

        data = {"accountId": 12345, "amount": 100, "type": "DEPOSIT"}
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Invalid accountId, accountId must be a valid UUID" in error

    def test_invalid_description_type(self):
        """Test that non-string descriptions are rejected."""
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": 100,
            "type": "DEPOSIT",
            "description": 12345,  # Not a string
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Description must be a string" in error

    def test_valid_with_decimal_amount(self):
        """Test that Decimal amounts are accepted."""
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": Decimal("100.50"),
            "type": "DEPOSIT",
            "description": "Test with Decimal",
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

    def test_case_insensitive_transaction_type(self):
        """Test that transaction types are case-insensitive."""
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": 100,
            "type": "deposit",
            "description": "Test with lowercase type",
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

        data["type"] = "DePoSiT"
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

    def test_valid_without_description(self):
        """
        Verifies that a transaction is valid when the optional description field is omitted.
        """
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": 100,
            "type": "DEPOSIT",
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

    def test_valid_transfer_transaction(self):
        """Test a valid TRANSFER transaction passes validation."""
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": 75.00,
            "type": "TRANSFER",
            "description": "Transfer to savings",
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

    def test_valid_adjustment_transaction(self):
        """Test a valid ADJUSTMENT transaction passes validation."""
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": 25.75,
            "type": "ADJUSTMENT",
            "description": "Fee reversal",
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None
