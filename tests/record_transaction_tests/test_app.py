import json
from unittest.mock import patch

from functions.record_transactions.record_transactions.app import lambda_handler
from functions.record_transactions.record_transactions.exceptions import (
    MissingSubClaimError,
    InvalidTokenError,
    AuthConfigurationError,
    AuthVerificationError,
)
from tests.record_transaction_tests.conftest import VALID_UUID


class TestLambdaHandler:
    def test_successful_transaction(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 201
        assert "transactionId" in response["body"]
        assert "Transaction recorded successfully" in response["body"]

    def test_missing_idempotency_key(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        valid_event["headers"].pop("Idempotency-Key")

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 400
        assert "Idempotency-Key header is required" in response["body"]

    def test_invalid_idempotency_key_format(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        valid_event["headers"]["Idempotency-Key"] = "not-a-uuid"

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 400
        assert "Idempotency-Key must be a valid UUID" in response["body"]

    def test_invalid_idempotency_key_length(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        short_idempotency_key = "short"
        valid_event["headers"]["Idempotency-Key"] = short_idempotency_key

        response = lambda_handler(valid_event, mock_context)
        response_body = json.loads(response["body"])
        assert response["statusCode"] == 400
        assert (
            "Idempotency-Key must be between 10 and 64 characters"
            in response_body["error"]
        )
        assert response_body["suggestion"]
        assert response_body["example"]

    def test_existing_transaction(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        mock_table.query.return_value = {
            "Items": [
                {"id": "existing-transaction-id", "idempotencyExpiration": 9999999999}
            ]
        }

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 201
        assert "existing-transaction-id" in response["body"]
        assert '"idempotent": true' in response["body"]

    def test_invalid_json_body(self, valid_event, mock_context, mock_table, mock_auth):
        valid_event["body"] = "invalid json"

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 400
        assert "Invalid JSON format" in response["body"]

    def test_missing_authorization(self, valid_event, mock_context, mock_table):
        valid_event["headers"].pop("Authorization")

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 401
        assert "Unauthorized" in response["body"]

    def test_invalid_token(self, valid_event, mock_context, mock_table, mock_auth):
        mock_auth.side_effect = InvalidTokenError("Invalid token")

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 401
        assert "Invalid authentication token" in response["body"]

    def test_missing_sub_claim(self, valid_event, mock_context, mock_table, mock_auth):
        mock_auth.side_effect = MissingSubClaimError("Missing sub claim")

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 401
        assert "Invalid authentication token" in response["body"]

    def test_auth_configuration_error(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        mock_auth.side_effect = AuthConfigurationError("Config error")

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 500
        assert "Server authentication configuration error" in response["body"]

    def test_auth_verification_error(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        mock_auth.side_effect = AuthVerificationError("Verification error")

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 500
        assert "Internal authentication error" in response["body"]

    def test_auth_unexpected_error(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        mock_auth.side_effect = Exception("Unknown error")

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 500
        assert "An unexpected error occurred during authentication." in response["body"]

    def test_database_error(self, valid_event, mock_context, mock_table, mock_auth):
        mock_table.query.side_effect = Exception("Database error")

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 500
        assert "Unable to verify transaction uniqueness" in response["body"]

    def test_invalid_transaction_data(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        valid_event["body"] = (
            '{"accountId": "'
            + VALID_UUID
            + '", "amount": "-100.50", "type": "DEPOSIT"}'
        )

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 400
        assert "Amount must be a positive number" in response["body"]

    def test_missing_required_fields(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        valid_event["body"] = '{"accountId": "' + VALID_UUID + '", "amount": "100.50"}'

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 400
        assert "Missing required fields" in response["body"]

    def test_invalid_transaction_type(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        valid_event["body"] = (
            '{"accountId": "'
            + VALID_UUID
            + '", "amount": "100.50", "type": "INVALID_TYPE"}'
        )

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 400
        assert "Invalid transaction type" in response["body"]

    def test_database_error_during_save(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        transaction_data = {
            "accountId": VALID_UUID,
            "amount": "100.50",
            "type": "DEPOSIT",
            "description": "Test transaction",
        }
        valid_event["body"] = json.dumps(transaction_data)

        mock_table.put_item.side_effect = Exception("Database connection error")

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 500
        response_body = json.loads(response["body"])
        assert "error" in response_body
        assert "Failed to process transaction" in response_body["error"]

    def test_unhandled_exception_handling(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        with patch(
            "functions.record_transactions.record_transactions.app.json.loads"
        ) as mock_json_loads:
            mock_json_loads.side_effect = MemoryError("Unexpected memory error")

            response = lambda_handler(valid_event, mock_context)

            assert response["statusCode"] == 500
            assert (
                response["body"]
                == '{"error": "Internal server error. Please contact support."}'
            )
