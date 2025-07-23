import uuid
from importlib import reload
from unittest.mock import patch

import pytest

from functions.get_transactions.get_transactions import app

# Constants needed by other test modules
VALID_UUID = str(uuid.uuid4())
TEST_USER_ID = str(uuid.uuid4())


@pytest.fixture
def mock_auth():
    """
    Pytest fixture that mocks the authentication request function.
    """
    with patch(
        "functions.get_transactions.get_transactions.app.authenticate_request"
    ) as mock:
        mock.return_value = TEST_USER_ID
        yield mock


@pytest.fixture
def valid_get_event():
    """
    Return a sample event dictionary simulating a valid GET transaction request.
    """
    return {
        "httpMethod": "GET",
        "path": "/transactions",
        "headers": {
            "Authorization": "Bearer valid-token",
        },
        "requestContext": {
            "requestId": str(uuid.uuid4()),
        },
    }


@pytest.fixture
def valid_get_transaction_event():
    """
    Return a sample event dictionary simulating a valid GET transaction by ID request.
    """
    transaction_id = VALID_UUID
    return {
        "httpMethod": "GET",
        "path": f"/transactions/{transaction_id}",
        "pathParameters": {"transaction_id": transaction_id},
        "headers": {
            "Authorization": "Bearer valid-token",
        },
        "requestContext": {
            "requestId": str(uuid.uuid4()),
        },
    }


@pytest.fixture(scope="function")
def get_transactions_app_with_mocked_tables(
    monkeypatch,
    dynamo_resource,
    mock_transactions_dynamo_table,
):
    transactions_table_name = mock_transactions_dynamo_table

    monkeypatch.setenv("TRANSACTIONS_TABLE_NAME", transactions_table_name)
    monkeypatch.setenv("ENVIRONMENT_NAME", "test")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "INFO")

    with patch("boto3.resource", return_value=dynamo_resource):
        reload(app)

        app.transactions_table = dynamo_resource.Table(transactions_table_name)

        yield app
