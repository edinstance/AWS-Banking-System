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
        valid_uuid = str(uuid.uuid4())
        assert is_valid_uuid(valid_uuid) is True

    def test_valid_uuid_uppercase(self):
        """Test that a valid UUID in uppercase still works."""
        valid_uuid = str(uuid.uuid4()).upper()
        assert is_valid_uuid(valid_uuid) is True

    def test_invalid_uuid_format(self):
        """
        Tests that is_valid_uuid returns False for an improperly formatted UUID string.
        """
        invalid_uuid = "not-a-uuid"
        assert is_valid_uuid(invalid_uuid) is False

    def test_uuid_wrong_length(self):
        """
        Tests that is_valid_uuid returns False for a UUID string with incorrect length.
        """
        too_short = "123e4567-e89b-12d3-a456"  # Incomplete UUID
        assert is_valid_uuid(too_short) is False

    def test_uuid_with_invalid_characters(self):
        """
        Tests that a UUID string containing invalid characters is correctly identified as invalid.
        """
        invalid_chars = "123e4567-e89b-12d3-a456-42661417400G"  # 'G' is not hex
        assert is_valid_uuid(invalid_chars) is False

    def test_none_value(self):
        """
        Tests that passing None to is_valid_uuid returns False.
        """
        assert is_valid_uuid(None) is False

    def test_empty_string(self):
        """
        Tests that passing an empty string to is_valid_uuid returns False.
        """
        assert is_valid_uuid("") is False

    def test_numeric_input(self):
        """
        Tests that passing a numeric input to is_valid_uuid returns False.
        """
        assert is_valid_uuid(12345) is False


class TestCreateResponse:
    def test_basic_response(self):
        """
        Tests that create_response returns a correctly formatted HTTP response for valid inputs.
        """
        status_code = 200
        body = {"message": "Success"}
        response = create_response(status_code, body)

        assert response["statusCode"] == status_code
        assert json.loads(response["body"]) == body
        assert response["headers"]["Content-Type"] == "application/json"

    def test_error_response(self):
        """
        Tests that create_response generates a correct error response with status code 400 and error body.
        """
        status_code = 400
        body = {"error": "Bad Request"}
        response = create_response(status_code, body)

        assert response["statusCode"] == status_code
        assert json.loads(response["body"]) == body

    def test_security_headers(self):
        """
        Verifies that the HTTP response includes required security headers.
        
        Asserts that the response contains "X-Content-Type-Options" set to "nosniff" and includes the "Strict-Transport-Security" header.
        """
        response = create_response(200, {})

        assert "X-Content-Type-Options" in response["headers"]
        assert response["headers"]["X-Content-Type-Options"] == "nosniff"
        assert "Strict-Transport-Security" in response["headers"]

    def test_json_serialization(self):
        """
        Tests that complex nested JSON objects are correctly serialized and deserialized in the response body.
        """
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
        """
        Tests that a valid DEPOSIT transaction with correct fields passes validation.
        """
        data = {
            "accountId": "account-12345",
            "amount": 100.50,
            "type": "DEPOSIT",
            "description": "Test deposit"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

    def test_valid_withdrawal_transaction(self):
        """
        Tests that a valid WITHDRAWAL transaction with positive amount and description passes validation.
        """
        data = {
            "accountId": "account-12345",
            "amount": 50.25,  # Now positive
            "type": "WITHDRAWAL",
            "description": "Test withdrawal"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

    def test_missing_required_fields(self):
        """
        Tests that the validator detects and reports missing required transaction fields.
        """
        # Missing accountId
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
        """
        Tests that transactions with invalid types are rejected and that the error message lists all valid transaction types.
        """
        data = {
            "accountId": "account-12345",
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
        """
        Tests that a transaction with a non-numeric amount is rejected as invalid.
        
        Verifies that the validation function returns False and an appropriate error message
        when the amount field is not a numeric value.
        """
        data = {
            "accountId": "account-12345",
            "amount": "not-a-number",
            "type": "DEPOSIT"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Invalid amount format" in error

    def test_negative_amount(self):
        """
        Tests that transactions with negative amounts are rejected for all transaction types.
        
        Verifies that providing a negative amount in the transaction data results in validation failure and an appropriate error message for both 'DEPOSIT' and 'WITHDRAWAL' types.
        """
        data = {
            "accountId": "account-12345",
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
        """
        Tests that a transaction with an amount of zero is rejected as invalid.
        
        Verifies that the validation function returns False and an appropriate error message when the amount is zero.
        """
        data = {
            "accountId": "account-12345",
            "amount": 0,
            "type": "DEPOSIT"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Amount must be a positive number" in error

    def test_invalid_account_id(self):
        """
        Tests that transactions with invalid account IDs are rejected by the validator.
        
        Verifies that account IDs that are too short or not strings cause validation to fail with an appropriate error message.
        """
        # Account ID too short
        data = {
            "accountId": "abc",  # Less than 5 characters
            "amount": 100,
            "type": "DEPOSIT"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Invalid accountId format" in error

        # Account ID not a string
        data = {
            "accountId": 12345,
            "amount": 100,
            "type": "DEPOSIT"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is False
        assert "Invalid accountId format" in error

    def test_invalid_description_type(self):
        """Test that non-string descriptions are rejected."""
        data = {
            "accountId": "account-12345",
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
            "accountId": "account-12345",
            "amount": Decimal("100.50"),
            "type": "DEPOSIT",
            "description": "Test with Decimal"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

    def test_case_insensitive_transaction_type(self):
        """
        Verifies that the transaction type field is validated in a case-insensitive manner.
        
        Ensures that both lowercase and mixed-case representations of valid transaction types are accepted by the validation function.
        """
        data = {
            "accountId": "account-12345",
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
        """
        Tests that a transaction is valid when the description field is omitted.
        """
        data = {
            "accountId": "account-12345",
            "amount": 100,
            "type": "DEPOSIT"
            # No description
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

    def test_valid_transfer_transaction(self):
        """
        Tests that a valid TRANSFER transaction with all required fields passes validation.
        """
        data = {
            "accountId": "account-12345",
            "amount": 75.00,
            "type": "TRANSFER",
            "description": "Transfer to savings"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None

    def test_valid_adjustment_transaction(self):
        """
        Tests that a valid ADJUSTMENT transaction with all required fields passes validation.
        """
        data = {
            "accountId": "account-12345",
            "amount": 25.75,
            "type": "ADJUSTMENT",
            "description": "Fee reversal"
        }
        is_valid, error = validate_transaction_data(data)
        assert is_valid is True
        assert error is None
