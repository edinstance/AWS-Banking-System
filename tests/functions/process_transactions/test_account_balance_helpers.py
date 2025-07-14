import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from functions.process_transactions.process_transactions.account_balance_helpers import (
    get_account_balance,
    update_account_balance,
)
from functions.process_transactions.process_transactions.exceptions import (
    BusinessLogicError,
)


class TestGetAccountBalance:

    def test_get_account_balance_success(self):
        account_id = str(uuid.uuid4())
        balance = Decimal("100")
        mock_logger = MagicMock()

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {"accountId": account_id, "balance": balance},
        }

        result = get_account_balance(str(account_id), mock_logger, mock_table)

        assert result == balance

    def test_get_account_balance_business_error(self):
        account_id = str(uuid.uuid4())
        mock_logger = MagicMock()

        mock_table = MagicMock()

        with pytest.raises(BusinessLogicError) as exception_info:
            get_account_balance(str(account_id), mock_logger, mock_table)

        assert exception_info.type is BusinessLogicError
        assert (
            str(exception_info.value) == f"Account {account_id} not found in database"
        )

    def test_get_account_balance_client_error(self):
        account_id = str(uuid.uuid4())
        mock_logger = MagicMock()

        mock_table = MagicMock()
        mock_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Connection Error"}},
            "Get Item",
        )

        with pytest.raises(SystemError) as exception_info:
            get_account_balance(str(account_id), mock_logger, mock_table)

        assert exception_info.type is SystemError
        assert "Failed to get account balance: " in str(exception_info.value)
        assert "Connection Error" in str(exception_info.value)

    def test_get_account_balance_generic_error(self):
        account_id = str(uuid.uuid4())
        mock_logger = MagicMock()

        mock_table = MagicMock()
        mock_table.get_item.side_effect = Exception("Something went wrong")

        with pytest.raises(SystemError) as exception_info:
            get_account_balance(str(account_id), mock_logger, mock_table)

        assert exception_info.type is SystemError
        assert (
            str(exception_info.value)
            == "Unexpected error getting account balance: Something went wrong"
        )


class TestUpdateAccountBalance:

    def test_get_account_balance_success(self):
        account_id = str(uuid.uuid4())
        new_balance = Decimal("100")
        mock_logger = MagicMock()
        mock_table = MagicMock()

        mock_table.get_item.return_value = {}
        result = update_account_balance(
            str(account_id), new_balance, mock_logger, mock_table
        )
        assert result is None

    def test_get_account_balance_client_error(self):
        account_id = str(uuid.uuid4())
        new_balance = Decimal("100")
        mock_logger = MagicMock()
        mock_table = MagicMock()

        mock_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Connection Error"}},
            "Get Item",
        )

        with pytest.raises(SystemError) as exception_info:
            update_account_balance(
                str(account_id), new_balance, mock_logger, mock_table
            )

        assert exception_info.type is SystemError
        assert "Failed to update account balance: " in str(exception_info.value)
        assert "Connection Error" in str(exception_info.value)

    def test_get_account_balance_generic_error(self):
        account_id = str(uuid.uuid4())
        new_balance = Decimal("100")
        mock_logger = MagicMock()
        mock_table = MagicMock()

        mock_table.update_item.side_effect = Exception("Something went wrong")

        with pytest.raises(SystemError) as exception_info:
            update_account_balance(
                str(account_id), new_balance, mock_logger, mock_table
            )

        assert exception_info.type is SystemError
        assert (
            str(exception_info.value)
            == "Unexpected error updating account balance: Something went wrong"
        )
