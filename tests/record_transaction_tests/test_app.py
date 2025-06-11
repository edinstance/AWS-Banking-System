import json
from unittest.mock import patch

from botocore.exceptions import ClientError

from functions.record_transactions.record_transactions.app import lambda_handler
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
        """
        Tests that the Lambda handler returns a 400 error when the Idempotency-Key header is missing from the request.
        """
        valid_event["headers"].pop("Idempotency-Key")

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 400
        assert "Idempotency-Key header is required" in response["body"]

    def test_invalid_idempotency_key_format(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        """
        Tests that providing a non-UUID idempotency key returns a 400 status with an appropriate error message.
        """
        valid_event["headers"]["Idempotency-Key"] = "not-a-uuid"

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 400
        assert "Idempotency-Key must be a valid UUID" in response["body"]

    def test_invalid_idempotency_key_length(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        """
        Tests that a request with an idempotency key of invalid length returns a 400 error with appropriate error, suggestion, and example fields in the response body.
        """
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
        """
        Tests that the Lambda handler returns a 201 response with the existing transaction ID and marks the response as idempotent when a transaction with the same idempotency key already exists.
        """
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
        """
        Tests that the Lambda handler returns a 400 status code and appropriate error message when the request body contains invalid JSON.
        """
        valid_event["body"] = "invalid json"

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 400
        assert "Invalid JSON format" in response["body"]

    def test_database_error(self, valid_event, mock_context, mock_table, mock_auth):
        """
        Tests that a database error during transaction uniqueness verification results in a 500 response.
        
        Simulates a database query failure and verifies that the Lambda handler returns a 500 status code with an appropriate error message.
        """
        mock_table.query.side_effect = Exception("Database error")

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 500
        assert "Unable to verify transaction uniqueness" in response["body"]

    def test_invalid_transaction_data(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        """
        Tests that the Lambda handler returns a 400 error when the transaction amount is negative.
        
        Verifies that submitting a transaction with a negative amount results in an appropriate error message indicating the amount must be positive.
        """
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
        """
        Tests that the Lambda handler returns a 400 error when required transaction fields are missing from the request body.
        """
        valid_event["body"] = '{"accountId": "' + VALID_UUID + '", "amount": "100.50"}'

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 400
        assert "Missing required fields" in response["body"]

    def test_invalid_transaction_type(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        """
        Tests that the Lambda handler returns a 400 status code when the transaction type is invalid.
        
        Verifies that providing an unsupported transaction type in the request body results in an error response indicating the invalid type.
        """
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
        """
        Tests that a database error during transaction saving results in a 500 response with an appropriate error message.
        """
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
        """
        Tests that the Lambda handler returns a 500 status code and a generic error message when an unexpected exception, such as a MemoryError during JSON parsing, occurs.
        """
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

    def test_client_error_during_save(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        """
        Tests that a ClientError during transaction save results in a 500 status code.
        
        Simulates a conditional check failure when saving a transaction to the database and verifies that the Lambda handler returns an internal server error response.
        """
        error_response = {
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "The conditional request failed",
            }
        }
        mock_table.put_item.side_effect = ClientError(error_response, "PutItem")

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 500
