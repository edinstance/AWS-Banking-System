import json
import uuid


from functions.record_transactions.record_transactions.helpers import (
    create_response,
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
        assert is_valid_uuid(123) is False


class TestCreateResponse:
    def test_successful_response(self):
        body = {"message": "Success"}
        response = create_response(200, body, "POST")

        assert response["statusCode"] == 200
        assert response["body"] == '{"message": "Success"}'
        assert response["headers"]["Content-Type"] == "application/json"
        assert response["headers"]["Access-Control-Allow-Methods"] == "POST"
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"

    def test_error_response(self):
        body = {"error": "Bad Request"}
        response = create_response(400, body, "GET")

        assert response["statusCode"] == 400
        assert response["body"] == '{"error": "Bad Request"}'
        assert response["headers"]["Access-Control-Allow-Methods"] == "GET"

    def test_empty_body(self):
        """
        Tests that create_response returns a 204 response with an empty JSON body and correct CORS headers when given an empty dictionary and the DELETE method.
        """
        response = create_response(204, {}, "DELETE")

        assert response["statusCode"] == 204
        assert response["body"] == "{}"
        assert response["headers"]["Access-Control-Allow-Methods"] == "DELETE"

    def test_complex_body(self):
        body = {"data": {"id": 1, "items": ["a", "b", "c"], "nested": {"key": "value"}}}
        response = create_response(200, body, "PUT")

        assert response["statusCode"] == 200
        assert '"items": ["a", "b", "c"]' in response["body"]
        assert '"nested": {"key": "value"}' in response["body"]
        assert response["headers"]["Access-Control-Allow-Methods"] == "PUT"


class TestValidateRequestHeaders:

    def test_no_idempotency_key(self):
        headers = {}

        response = validate_request_headers(headers)
        response_body = json.loads(response["body"])

        assert response["statusCode"] == 400
        assert "error" in response_body
        assert (
            response_body["error"]
            == "Idempotency-Key header is required for transaction creation"
        )

    def test_short_idempotency_key(self):
        headers = {"idempotency-key": "key"}

        response = validate_request_headers(headers)
        response_body = json.loads(response["body"])

        assert response["statusCode"] == 400
        assert "error" in response_body
        assert (
            response_body["error"]
            == "Idempotency-Key must be between 10 and 64 characters"
        )

    def test_incorrect_idempotency_key(self):
        headers = {"idempotency-key": "long-but-invalid-key"}

        response = validate_request_headers(headers)
        response_body = json.loads(response["body"])

        assert response["statusCode"] == 400
        assert "error" in response_body
        assert response_body["error"] == "Idempotency-Key must be a valid UUID"

    def test_successful_idempotency_key(self):
        headers = {"idempotency-key": str(uuid.uuid4())}

        response = validate_request_headers(headers)

        assert response is None
