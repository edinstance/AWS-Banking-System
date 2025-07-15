import uuid
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from checks import check_account_exists_in_database, check_user_owns_account


class TestCheckAccountExists:

    def test_check_account_success(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"accountId": str(uuid.uuid4())}}
        result = check_account_exists_in_database(str(uuid.uuid4()), mock_table)

        assert result is True

    def test_check_account_failure(self):
        mock_table = MagicMock()
        mock_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Connection Error"}},
            "Get Item",
        )
        result = check_account_exists_in_database(str(uuid.uuid4()), mock_table)
        assert result is False

    def test_no_item_returned(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        result = check_account_exists_in_database(str(uuid.uuid4()), mock_table)
        assert result is False


class TestCheckUserOwnsAccount:

    def test_check_user_success(self):
        user_id = str(uuid.uuid4())

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {"accountId": str(uuid.uuid4()), "userId": user_id}
        }

        result = check_user_owns_account(str(uuid.uuid4()), user_id, mock_table)

        assert result is True

    def test_user_id_mismatch(self):
        user_id = str(uuid.uuid4())
        account_id = str(uuid.uuid4())

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {"accountId": account_id, "userId": str(uuid.uuid4())}
        }

        result = check_user_owns_account(account_id, user_id, mock_table)

        assert result is False

    def test_no_item_returned(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        result = check_user_owns_account(
            str(uuid.uuid4()), str(uuid.uuid4()), mock_table
        )

        assert result is False

    def test_client_error(self):
        mock_table = MagicMock()
        mock_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Connection Error"}},
            "Get Item",
        )

        result = check_user_owns_account(
            str(uuid.uuid4()), str(uuid.uuid4()), mock_table
        )
        assert result is False
