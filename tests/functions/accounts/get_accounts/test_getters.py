import uuid

import pytest
from aws_lambda_powertools.event_handler.exceptions import ForbiddenError, NotFoundError
from botocore.exceptions import ClientError

from functions.accounts.get_accounts.get_accounts.getters import (
    get_all_accounts,
    get_account_by_id,
)


class TestGetAllAccounts:

    def test_client_error(self, magic_mock_accounts_table, mock_logger):
        magic_mock_accounts_table.query.side_effect = ClientError(
            {"Error": {"Code": "Error", "Message": "Test query"}}, "query"
        )

        user_id = str(uuid.uuid4())
        with pytest.raises(ClientError) as exception_info:
            get_all_accounts(user_id, magic_mock_accounts_table, mock_logger)

        assert exception_info.type is ClientError
        assert (
            "An error occurred (Error) when calling the query operation: Test query"
            == str(exception_info.value)
        )

    def test_success(self, magic_mock_accounts_table, mock_logger):
        test_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        magic_mock_accounts_table.query.return_value = {"Items": [{"id": test_id}]}

        response = get_all_accounts(user_id, magic_mock_accounts_table, mock_logger)

        assert response[0]["id"] == test_id


class TestGetAccountById:

    def test_client_error(self, magic_mock_accounts_table, mock_logger):
        magic_mock_accounts_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "Error", "Message": "Test query"}}, "query"
        )

        user_id = str(uuid.uuid4())
        account_id = str(uuid.uuid4())

        with pytest.raises(ClientError) as exception_info:
            get_account_by_id(
                user_id, account_id, magic_mock_accounts_table, mock_logger
            )

        assert exception_info.type is ClientError
        assert (
            "An error occurred (Error) when calling the query operation: Test query"
            == str(exception_info.value)
        )

    def test_access_denied_error(self, magic_mock_accounts_table, mock_logger):
        account_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        magic_mock_accounts_table.get_item.return_value = {
            "Item": {
                "accountId": account_id,
            }
        }

        with pytest.raises(ForbiddenError) as exception_info:
            get_account_by_id(
                user_id, account_id, magic_mock_accounts_table, mock_logger
            )

        assert exception_info.type is ForbiddenError
        assert "Access denied." == str(exception_info.value)

    def test_not_found_error(self, magic_mock_accounts_table, mock_logger):
        account_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        magic_mock_accounts_table.get_item.return_value = {"Item": {}}

        with pytest.raises(NotFoundError) as exception_info:
            get_account_by_id(
                user_id, account_id, magic_mock_accounts_table, mock_logger
            )

        assert exception_info.type is NotFoundError
        assert "Account not found" == str(exception_info.value)

    def test_success(self, magic_mock_accounts_table, mock_logger):
        account_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        magic_mock_accounts_table.get_item.return_value = {
            "Item": {
                "accountId": account_id,
                "userId": user_id,
            }
        }

        response = get_account_by_id(
            user_id, account_id, magic_mock_accounts_table, mock_logger
        )

        assert response["accountId"] == account_id
