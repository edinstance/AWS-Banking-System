import uuid

import pytest
from aws_lambda_powertools.event_handler.exceptions import ForbiddenError, NotFoundError
from botocore.exceptions import ClientError

from functions.transactions.get_transactions.get_transactions.getters import (
    get_all_transactions,
    get_transaction_by_id,
)


class TestGetAllTransactions:

    def test_client_error(self, magic_mock_transactions_table, mock_logger):
        """
        Test that get_all_transactions raises a ClientError when the transactions table query fails.
        """
        magic_mock_transactions_table.query.side_effect = ClientError(
            {"Error": {"Code": "Error", "Message": "Test query"}}, "query"
        )

        user_id = str(uuid.uuid4())
        with pytest.raises(ClientError) as exception_info:
            get_all_transactions(user_id, magic_mock_transactions_table, mock_logger)

        assert exception_info.type is ClientError
        assert (
            "An error occurred (Error) when calling the query operation: Test query"
            == str(exception_info.value)
        )

    def test_success(self, magic_mock_transactions_table, mock_logger):
        """
        Tests that `get_all_transactions` returns the expected transaction data when the query is successful.
        """
        test_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        magic_mock_transactions_table.query.return_value = {"Items": [{"id": test_id}]}

        response = get_all_transactions(
            user_id, magic_mock_transactions_table, mock_logger
        )

        assert response[0]["id"] == test_id


class TestGetTransactionById:

    def test_client_error(self, magic_mock_transactions_table, mock_logger):
        """
        Test that get_transaction_by_id propagates a ClientError raised by the transactions table query.
        """
        magic_mock_transactions_table.query.side_effect = ClientError(
            {"Error": {"Code": "Error", "Message": "Test query"}}, "query"
        )

        user_id = str(uuid.uuid4())
        transaction_id = str(uuid.uuid4())

        with pytest.raises(ClientError) as exception_info:
            get_transaction_by_id(
                user_id, transaction_id, magic_mock_transactions_table, mock_logger
            )

        assert exception_info.type is ClientError
        assert (
            "An error occurred (Error) when calling the query operation: Test query"
            == str(exception_info.value)
        )

    def test_access_denied_error(self, magic_mock_transactions_table, mock_logger):
        """
        Test that `get_transaction_by_id` raises a `ForbiddenError` when the transaction exists but the user is not authorised to access it.
        """
        transaction_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        magic_mock_transactions_table.query.return_value = {
            "Items": [
                {
                    "id": transaction_id,
                }
            ]
        }

        with pytest.raises(ForbiddenError) as exception_info:
            get_transaction_by_id(
                user_id, transaction_id, magic_mock_transactions_table, mock_logger
            )

        assert exception_info.type is ForbiddenError
        assert "Access denied." == str(exception_info.value)

    def test_not_found_error(self, magic_mock_transactions_table, mock_logger):
        """
        Test that `get_transaction_by_id` raises a `NotFoundError` when no transaction is found for the given transaction ID and user ID.
        """
        transaction_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        magic_mock_transactions_table.query.return_value = {"Items": []}

        with pytest.raises(NotFoundError) as exception_info:
            get_transaction_by_id(
                user_id, transaction_id, magic_mock_transactions_table, mock_logger
            )

        assert exception_info.type is NotFoundError
        assert "Transaction not found" == str(exception_info.value)

    def test_success(self, magic_mock_transactions_table, mock_logger):
        """
        Tests that `get_transaction_by_id` returns the correct transaction when the user ID and transaction ID match an existing item.
        """
        transaction_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        magic_mock_transactions_table.query.return_value = {
            "Items": [
                {
                    "id": transaction_id,
                    "userId": user_id,
                }
            ]
        }

        response = get_transaction_by_id(
            user_id, transaction_id, magic_mock_transactions_table, mock_logger
        )

        assert response["id"] == transaction_id
