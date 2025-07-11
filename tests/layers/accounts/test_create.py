import datetime
import uuid
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from create import create_account_if_not_exists

UTC = datetime.timezone.utc


def test_create_account_if_not_exists_success(monkeypatch):
    mock_table = MagicMock()
    mock_logger = MagicMock()
    account_id = uuid.uuid4()
    user_id = uuid.uuid4()

    monkeypatch.setattr(uuid, "uuid4", lambda: account_id)

    returned_account_id = create_account_if_not_exists(
        table=mock_table,
        logger=mock_logger,
        user_id=str(user_id),
    )

    mock_table.put_item.assert_called_once()

    assert returned_account_id == str(account_id)


def test_create_account_if_not_exists_missing_user_id():
    mock_table = MagicMock()
    mock_logger = MagicMock()

    with pytest.raises(ValueError, match="user_id is required"):
        create_account_if_not_exists(
            table=mock_table,
            logger=mock_logger,
            user_id="",
        )

    mock_table.put_item.assert_not_called()
    mock_logger.error.assert_not_called()


def test_create_account_if_not_exists_dynamodb_client_error():
    mock_logger = MagicMock()
    mock_table = MagicMock()
    user_id = uuid.uuid4()

    simulated_error_message = "ProvisionedThroughputExceededException"
    simulated_client_error = ClientError(
        {
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": simulated_error_message,
            }
        },
        "PutItem",
    )
    mock_table.put_item.side_effect = simulated_client_error

    with pytest.raises(ClientError) as exc_info:
        create_account_if_not_exists(
            table=mock_table,
            logger=mock_logger,
            user_id=str(user_id),
        )

    mock_table.put_item.assert_called_once()

    mock_logger.error.assert_called_once()
    error_call_args = mock_logger.error.call_args[0]

    assert "ProvisionedThroughputExceededException" in error_call_args[0]
    assert mock_logger.error.call_args[1]["exc_info"] is True
    assert exc_info.value == simulated_client_error
