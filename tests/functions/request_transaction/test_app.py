import json
from unittest.mock import patch

from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError
from botocore.exceptions import ClientError

from functions.request_transaction.request_transaction.app import lambda_handler
from tests.functions.request_transaction.conftest import VALID_UUID


class TestLambdaHandler:
    def test_successful_transaction(
        self, mock_table, valid_event, mock_context, mock_auth
    ):
        response = lambda_handler(valid_event, mock_context)
        assert response["statusCode"] == 201
        assert "transactionId" in response["body"]
        assert "Transaction requested successfully" in response["body"]

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
        Verify that a request with an idempotency key of invalid length returns a 400 response containing error, suggestion, and example fields in the response body.
        """
        short_idempotency_key = "short"
        valid_event["headers"]["Idempotency-Key"] = short_idempotency_key

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 400
        assert (
            "Idempotency-Key must be between 10 and 64 characters" in response["body"]
        )

    def test_invalid_json_body(self, valid_event, mock_context, mock_table, mock_auth):
        """
        Test that the Lambda handler returns a 400 status code and an error message when the request body contains invalid JSON.
        """
        valid_event["body"] = "invalid json"

        response = lambda_handler(valid_event, mock_context)

        assert response["statusCode"] == 400
        assert "Invalid JSON format" in response["body"]

    def test_invalid_transaction_data(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        """
        Test that the Lambda handler returns a 400 error when a transaction with a negative amount is submitted.

        Verifies that the response includes an error message stating the amount must be positive.
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

        response_body = json.loads(response["body"])

        assert response["statusCode"] == 500
        assert (
            response_body["message"]
            == "Failed to process transaction. Please try again."
        )

    def test_client_error_during_save(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        """
        Verify that a ClientError during transaction save causes the Lambda handler to return a 500 internal server error response.

        Simulates a conditional check failure when saving a transaction to the database and asserts that the handler responds with a 500 status code.
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

    def test_auth_error_returned(self, valid_event, mock_context, mock_table):
        """
        Test that the Lambda handler returns the authentication error response unchanged when authentication fails.
        """
        from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

        auth_error = UnauthorizedError("Authentication failed")

        with patch(
            "functions.request_transaction.request_transaction.app.authenticate_request"
        ) as mock_auth:
            mock_auth.side_effect = auth_error

            response = lambda_handler(valid_event, mock_context)
            body = json.loads(response["body"])

            assert response["statusCode"] == 401
            assert body["message"] == "Authentication failed"

    def test_no_user_id_no_auth_error(self, valid_event, mock_context, mock_table):
        """
        Test that the Lambda handler returns a 401 error when authentication fails to determine user identity.

        This test ensures that if the authentication function raises an UnauthorizedError with the message
        "Unauthorized: User identity could not be determined", the handler responds with a 401 status code
        and the appropriate error message.
        """
        auth_error = UnauthorizedError(
            "Unauthorized: User identity could not be determined"
        )

        with patch(
            "functions.request_transaction.request_transaction.app.authenticate_request"
        ) as mock_auth:
            mock_auth.side_effect = auth_error

            response = lambda_handler(valid_event, mock_context)

            assert response["statusCode"] == 401
            assert (
                "Unauthorized: User identity could not be determined"
                in response["body"]
            )

    def test_idempotency_error_returns_dict(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        error_response = {
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "The conditional request failed",
            }
        }
        mock_table.put_item.side_effect = ClientError(error_response, "PutItem")

        expected_response = {"message": "Custom error response"}

        with patch(
            "functions.request_transaction.request_transaction.app.handle_idempotency_error",
            return_value=expected_response,
        ):
            response = lambda_handler(valid_event, mock_context)

            response_body = json.loads(response["body"])

            assert response_body == expected_response

    def test_idempotency_error_returns_tuple(
        self, valid_event, mock_context, mock_table, mock_auth
    ):
        error_response = {
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "The conditional request failed",
            }
        }
        mock_table.put_item.side_effect = ClientError(error_response, "PutItem")

        expected_response = ({"message": "Transaction already processed."}, 409)

        with patch(
            "functions.request_transaction.request_transaction.app.handle_idempotency_error",
            return_value=expected_response,
        ):
            response = lambda_handler(valid_event, mock_context)

            assert response["statusCode"] == 409

            response_body = json.loads(response["body"])

            assert response_body == expected_response[0]
