import uuid

import pytest
from aws_lambda_powertools.event_handler.exceptions import BadRequestError

from functions.request_transaction.request_transaction.transaction_helpers import (
    is_valid_uuid,
    validate_request_headers,
)

# Test constants
VALID_UUID = "123e4567-e89b-12d3-a456-426614174000"
INVALID_UUID = "not-a-uuid"


class TestIsValidUUID:
    def test_valid_uuid_v4(self):
        """Test that a valid UUID v4 string returns True."""
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
        assert is_valid_uuid(INVALID_UUID) is False

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

    def test_non_string_input(self):
        """
        Test that passing a non-string input to is_valid_uuid returns False.
        """
        assert is_valid_uuid(123) is False


class TestValidateRequestHeaders:

    def test_no_idempotency_key(self):
        """
        Test that omitting the "Idempotency-Key" header results in a 400 error response indicating the header is required.
        """
        headers = {}

        with pytest.raises(BadRequestError) as exception_info:
            validate_request_headers(headers)

        assert exception_info.type is BadRequestError
        assert (
            exception_info.value.msg
            == "Idempotency-Key header is required for transaction creation"
        )

    def test_short_idempotency_key(self):
        headers = {"idempotency-key": "key"}

        with pytest.raises(BadRequestError) as exception_info:
            validate_request_headers(headers)

        assert exception_info.type is BadRequestError
        assert (
            exception_info.value.msg
            == "Idempotency-Key must be between 10 and 64 characters"
        )

    def test_incorrect_idempotency_key(self):
        """
        Test that an invalid 'idempotency-key' header value raises a BadRequestError indicating the key must be a valid UUID.
        """
        headers = {"idempotency-key": "long-but-invalid-key"}

        with pytest.raises(BadRequestError) as exception_info:
            validate_request_headers(headers)

        assert exception_info.type is BadRequestError
        assert exception_info.value.msg == "Idempotency-Key must be a valid UUID"

    def test_successful_idempotency_key(self):
        """
        Test that a valid 'idempotency-key' header passes validation without raising an error.
        """
        headers = {"idempotency-key": str(uuid.uuid4())}

        response = validate_request_headers(headers)

        assert response is None
