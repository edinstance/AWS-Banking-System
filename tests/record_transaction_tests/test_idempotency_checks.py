import json
from unittest.mock import patch

from botocore.exceptions import ClientError

from functions.record_transactions.record_transactions.idempotency import (
    handle_idempotency_error,
)


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
        Tests that a conditional check failure during idempotency error handling returns a 500 status code and an appropriate error message indicating the transaction was already processed.
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

            assert result["statusCode"] == 500
            assert (
                "Error retrieving existing transaction"
                in json.loads(result["body"])["message"]
            )

    def test_conditional_check_existing_transaction(self, mock_table, mock_logger):
        """
        Tests that a conditional check failure with an existing transaction returns a 409 status.

        Verifies that when a `ConditionalCheckFailedException` occurs and an existing transaction is found,
        the error handler responds with a 409 status code and includes the existing transaction ID in the response.
        """
        mock_error = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem"
        )

        existing_transaction = {"id": "existing-txn-123"}
        with patch(
            "functions.record_transactions.record_transactions.idempotency.check_existing_transaction",
            return_value=existing_transaction,
        ):
            result = handle_idempotency_error(
                self.TEST_IDEMPOTENCY_KEY,
                mock_table,
                mock_logger,
                self.TEST_TRANSACTION_ID,
                mock_error,
            )

            assert result["statusCode"] == 409
            response_body = json.loads(result["body"])
            assert "Transaction already processed" in response_body["message"]
            assert response_body["transactionId"] == "existing-txn-123"
            assert response_body["idempotent"] is True
