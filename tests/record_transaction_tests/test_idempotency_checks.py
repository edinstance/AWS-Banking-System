import json
from unittest.mock import patch

from botocore.exceptions import ClientError

from functions.record_transactions.record_transactions.idempotency import (
    handle_idempotency_check,
    handle_idempotency_error,
)


class TestIdempotencyChecks:

    def test_existing_transaction(self, mock_logger, mock_table, mock_create_response):
        """
        Tests that an existing transaction for a given idempotency key returns a 201 response with the correct transaction details and idempotency status.
        """
        idempotency_key = "test-key-123"
        existing_transaction = {"id": "transaction-123"}
        expected_response_body = {
            "message": "Transaction recorded successfully!",
            "transactionId": "transaction-123",
            "idempotent": True,
        }

        mock_create_response.return_value = {
            "statusCode": 201,
            "body": json.dumps(expected_response_body),
            "headers": {},
        }

        with patch(
            "functions.record_transactions.record_transactions.idempotency.check_existing_transaction",
            return_value=existing_transaction,
        ) as mock_check_existing_transaction:
            response = handle_idempotency_check(
                idempotency_key, mock_table, mock_logger
            )

            mock_check_existing_transaction.assert_called_once_with(
                idempotency_key, mock_table, mock_logger
            )

            mock_create_response.assert_called_once_with(
                201, expected_response_body, "OPTIONS,POST"
            )

            assert response["statusCode"] == 201
            assert json.loads(response["body"]) == expected_response_body

    def test_no_existing_transaction(self, mock_table, mock_logger):
        """
        Tests that handle_idempotency_check returns None when no existing transaction is found for the given idempotency key.
        """
        idempotency_key = "test-key-456"

        with patch(
            "functions.record_transactions.record_transactions.idempotency.check_existing_transaction",
            return_value=None,
        ) as mock_check_existing_transaction:
            response = handle_idempotency_check(
                idempotency_key, mock_table, mock_logger
            )

            mock_check_existing_transaction.assert_called_once_with(
                idempotency_key, mock_table, mock_logger
            )
            assert response is None

    def test_idempotency_exception_handling(
        self, mock_table, mock_logger, mock_create_response
    ):
        """
        Tests that handle_idempotency_check returns a 500 response with an appropriate error
        message when an exception occurs during the idempotency check.
        """
        idempotency_key = "test-key-789"
        expected_error_body = {
            "error": "Unable to verify transaction uniqueness. Please try again."
        }
        mock_create_response.return_value = {
            "statusCode": 500,
            "body": json.dumps(expected_error_body),
            "headers": {},
        }

        with patch(
            "functions.record_transactions.record_transactions.idempotency.check_existing_transaction",
            side_effect=Exception("Error checking idempotency"),
        ) as mock_check_existing_transaction:
            response = handle_idempotency_check(
                idempotency_key, mock_table, mock_logger
            )

            mock_check_existing_transaction.assert_called_once_with(
                idempotency_key, mock_table, mock_logger
            )

            assert response["statusCode"] == 500
            assert json.loads(response["body"]) == expected_error_body


class TestIdempotencyErrors:
    TEST_IDEMPOTENCY_KEY = "test-idempotency-key-123"
    TEST_TRANSACTION_ID = "txn-abc-123"

    def test_generic_exception(self, mock_table, mock_logger):
        """
        Tests that a generic ClientError during idempotency handling returns a 500 status code and an appropriate error message.
        """
        mock_error = ClientError({"Error": {"Code": "Generic Error"}}, "PutItem")

        result = handle_idempotency_error(
            self.TEST_IDEMPOTENCY_KEY,
            mock_table,
            mock_logger,
            self.TEST_TRANSACTION_ID,
            mock_error,
        )

        assert result["statusCode"] == 500
        assert "Failed to process transaction" in json.loads(result["body"])["error"]

    def test_conditional_check_error(self, mock_table, mock_logger):
        """
        Tests that a conditional check failure during idempotency error handling returns a 409 status code and an appropriate error message indicating the transaction was already processed.
        """
        mock_error = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem"
        )
        with patch(
            "functions.record_transactions.record_transactions.idempotency.check_existing_transaction",
            side_effect=Exception("New error"),
        ):
            result = handle_idempotency_error(
                self.TEST_IDEMPOTENCY_KEY,
                mock_table,
                mock_logger,
                self.TEST_TRANSACTION_ID,
                mock_error,
            )

            assert result["statusCode"] == 409
            assert (
                "Transaction already processed" in json.loads(result["body"])["error"]
            )

    def test_conditional_check_existing_transaction(self, mock_table, mock_logger):
        """
        Tests that a conditional check failure with an existing transaction returns a 409 status.

        Verifies that when a `ConditionalCheckFailedException` occurs and an existing transaction is found, the error handler responds with a 409 status code and an appropriate error message indicating the transaction was already processed.
        """
        mock_error = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem"
        )
        with patch(
            "functions.record_transactions.record_transactions.idempotency.check_existing_transaction",
            return_value=True,
        ):
            result = handle_idempotency_error(
                self.TEST_IDEMPOTENCY_KEY,
                mock_table,
                mock_logger,
                self.TEST_TRANSACTION_ID,
                mock_error,
            )

            assert result["statusCode"] == 409
            assert (
                "Transaction already processed" in json.loads(result["body"])["error"]
            )
