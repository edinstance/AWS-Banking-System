import uuid

import pytest
from botocore.exceptions import ClientError

from functions.get_transactions.get_transactions.getters import (
    get_all_transactions,
    get_transaction_by_id,
)


class TestGetAllTransactions:

    def test_client_error(self, magic_mock_transactions_table, mock_logger):
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
        test_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        magic_mock_transactions_table.query.return_value = {"Items": [{"id": test_id}]}

        response = get_all_transactions(
            user_id, magic_mock_transactions_table, mock_logger
        )

        assert response[0]["id"] == test_id


class TestGetTransactionById:

    def test_client_error(self, magic_mock_transactions_table, mock_logger):
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

    def test_value_error(self, magic_mock_transactions_table, mock_logger):
        transaction_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        magic_mock_transactions_table.query.return_value = {
            "Items": [
                {
                    "id": transaction_id,
                }
            ]
        }

        with pytest.raises(ValueError) as exception_info:
            get_transaction_by_id(
                user_id, transaction_id, magic_mock_transactions_table, mock_logger
            )

        assert exception_info.type is ValueError
        assert "Invalid transaction ID or user ID" == str(exception_info.value)

    def test_success(self, magic_mock_transactions_table, mock_logger):
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
