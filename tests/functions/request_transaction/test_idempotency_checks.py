from unittest.mock import patch

import pytest
from aws_lambda_powertools.event_handler.exceptions import InternalServerError
from botocore.exceptions import ClientError

from functions.request_transaction.request_transaction.idempotency import (
    handle_idempotency_error,
)


class TestIdempotencyErrors:
    TEST_IDEMPOTENCY_KEY = "test-idempotency-key-123"
    TEST_TRANSACTION_ID = "txn-abc-123"

    def test_generic_exception(self, mock_table, mock_logger):
        """
        Test that a generic ClientError during idempotency handling raises an InternalServerError with the correct message.
        """
        mock_error = ClientError({"Error": {"Code": "Generic Error"}}, "PutItem")

        with pytest.raises(InternalServerError) as exception_info:
            handle_idempotency_error(
                self.TEST_IDEMPOTENCY_KEY,
                mock_table,
                mock_logger,
                self.TEST_TRANSACTION_ID,
                mock_error,
            )

        assert exception_info.type == InternalServerError
        assert (
            exception_info.value.msg
            == "Failed to process transaction. Please try again."
        )

    def test_conditional_check_error(self, mock_table, mock_logger):
        """
        Verify that a conditional check failure during idempotency error handling raises an InternalServerError when retrieval of the existing transaction fails.
        
        Simulates a DynamoDB ConditionalCheckFailedException and forces the retrieval of the existing transaction to raise an exception, asserting that the resulting error is an InternalServerError with the expected message.
        """
        mock_error = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem"
        )
        with patch(
            "functions.request_transaction.request_transaction.idempotency.check_existing_transaction",
            side_effect=Exception("New error"),
        ):
            with pytest.raises(InternalServerError) as exception_info:
                handle_idempotency_error(
                    self.TEST_IDEMPOTENCY_KEY,
                    mock_table,
                    mock_logger,
                    self.TEST_TRANSACTION_ID,
                    mock_error,
                )

        assert exception_info.type == InternalServerError
        assert exception_info.value.msg == "Error retrieving existing transaction."

    def test_conditional_check_existing_transaction(self, mock_table, mock_logger):
        """
        Test that a conditional check failure with an existing transaction returns a 409 status and transaction details.
        
        Simulates a conditional check failure during idempotency error handling where an existing transaction is found. Verifies that the response includes a 409 status code, a message indicating the transaction was already processed, and the existing transaction ID.
        """
        mock_error = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem"
        )

        existing_transaction = {"id": "existing-txn-123"}
        with patch(
            "functions.request_transaction.request_transaction.idempotency.check_existing_transaction",
            return_value=existing_transaction,
        ):
            result = handle_idempotency_error(
                self.TEST_IDEMPOTENCY_KEY,
                mock_table,
                mock_logger,
                self.TEST_TRANSACTION_ID,
                mock_error,
            )

            assert result[1] == 409
            assert result[0]["message"] == "Transaction already processed."
            assert result[0]["transactionId"] == "existing-txn-123"
