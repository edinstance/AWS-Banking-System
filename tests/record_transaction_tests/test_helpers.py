import json
import uuid
from decimal import Decimal

from functions.record_transactions.app import (
    is_valid_uuid,
    create_response,
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
        """Test that an improperly formatted UUID returns False."""
        invalid_uuid = "not-a-uuid"
        assert is_valid_uuid(invalid_uuid) is False

    def test_uuid_wrong_length(self):
        """Test that a string of the wrong length returns False."""
        too_short = "123e4567-e89b-12d3-a456"  # Incomplete UUID
        assert is_valid_uuid(too_short) is False

    def test_uuid_with_invalid_characters(self):
        """Test that a UUID with invalid characters returns False."""
        invalid_chars = "123e4567-e89b-12d3-a456-42661417400G"  # 'G' is not hex
        assert is_valid_uuid(invalid_chars) is False

    def test_none_value(self):
        """Test that None returns False."""
        assert is_valid_uuid(None) is False

    def test_empty_string(self):
        """Test that an empty string returns False."""
        assert is_valid_uuid("") is False

    def test_numeric_input(self):
        """Test that a numeric input returns False."""
        assert is_valid_uuid(12345) is False


class TestCreateResponse:
    def test_basic_response(self):
        """Test creating a basic response with valid inputs."""
        status_code = 200
        body = {"message": "Success"}
        response = create_response(status_code, body)

        assert response["statusCode"] == status_code
        assert json.loads(response["body"]) == body
        assert response["headers"]["Content-Type"] == "application/json"

    def test_error_response(self):
        """Test creating an error response."""
        status_code = 400
        body = {"error": "Bad Request"}
        response = create_response(status_code, body)

        assert response["statusCode"] == status_code
        assert json.loads(response["body"]) == body

    def test_security_headers(self):
        """Test that security headers are included in the response."""
        response = create_response(200, {})

        assert "X-Content-Type-Options" in response["headers"]
        assert response["headers"]["X-Content-Type-Options"] == "nosniff"
        assert "Strict-Transport-Security" in response["headers"]

    def test_json_serialization(self):
        """Test that complex JSON is properly serialized."""
        body = {
            "id": "12345",
            "nested": {"key": "value"},
            "list": [1, 2, 3]
        }
        response = create_response(200, body)

        # Deserialize to verify integrity
        deserialized = json.loads(response["body"])
        assert deserialized == body


class TestValidateTransactionData:
    def test_valid_deposit_transaction(self):
        """Test a valid DEPOSIT transaction passes validation."""
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": 100.50,
            "type": "DEPOSIT",
            "description": "Test deposit"
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
            "description": "Test withdrawal"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

    def test_missing_required_fields(self):
        """Test that missing required fields are detected."""
        data = {
            "amount": 100,
            "type": "DEPOSIT"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Missing required fields" in error
        assert "accountId" in error

        # Missing multiple fields
        data = {"type": "DEPOSIT"}
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "accountId" in error
        assert "amount" in error

    def test_invalid_transaction_type(self):
        """Test that invalid transaction types are rejected."""
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": 100,
            "type": "INVALID_TYPE"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Invalid transaction type" in error

        # Check that all valid types are mentioned in the error
        for valid_type in VALID_TRANSACTION_TYPES:
            assert valid_type in error

    def test_invalid_amount_format(self):
        """Test that non-numeric amounts are rejected."""
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": "not-a-number",
            "type": "DEPOSIT"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Invalid amount format" in error

    def test_negative_amount(self):
        """Test that negative amounts are rejected for all transaction types."""
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": -100,
            "type": "DEPOSIT"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Amount must be a positive number" in error

        # Also test for WITHDRAWAL
        data["type"] = "WITHDRAWAL"
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Amount must be a positive number" in error

    def test_zero_amount(self):
        """Test that zero amounts are rejected."""
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": 0,
            "type": "DEPOSIT"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Amount must be a positive number" in error

    def test_invalid_account_id(self):
        """Test that invalid account IDs are rejected."""
        # Account ID too short
        data = {
            "accountId": "abs121",
            "amount": 100,
            "type": "DEPOSIT"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Invalid accountId, accountId must be a valid UUID" in error

        # Account ID not a string
        data = {
            "accountId": 12345,
            "amount": 100,
            "type": "DEPOSIT"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Invalid accountId, accountId must be a valid UUID" in error

    def test_invalid_description_type(self):
        """Test that non-string descriptions are rejected."""
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": 100,
            "type": "DEPOSIT",
            "description": 12345  # Not a string
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
            "description": "Test with Decimal"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

    def test_case_insensitive_transaction_type(self):
        """Test that transaction types are case-insensitive."""
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": 100,
            "type": "deposit",  # Lowercase
            "description": "Test with lowercase type"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

        # Mixed case
        data["type"] = "DePoSiT"
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

    def test_valid_without_description(self):
        """Test that description is optional."""
        data = {
            "accountId": str(uuid.uuid4()),
            "amount": 100,
            "type": "DEPOSIT"
            # No description
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
            "description": "Transfer to savings"
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
            "description": "Fee reversal"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None
