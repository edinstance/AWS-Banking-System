import uuid
from importlib import reload
from unittest.mock import patch

import pytest

from functions.transactions.get_transactions.get_transactions import app

VALID_UUID = str(uuid.uuid4())
TEST_USER_ID = str(uuid.uuid4())


@pytest.fixture
def mock_auth():
    """
    Pytest fixture that replaces the authentication function with a mock returning a fixed test user ID.

    Yields:
        The mocked authentication function.
    """
    with patch(
        "functions.transactions.get_transactions.get_transactions.app.authenticate_request"
    ) as mock:
        mock.return_value = TEST_USER_ID
        yield mock


@pytest.fixture
def valid_get_event():
    """
    Return a dictionary representing a valid HTTP GET event for retrieving all transactions.

    The returned event includes the HTTP method, endpoint path, authorisation header, and a unique request ID in the request context.
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
    Generate a sample event dictionary representing a valid HTTP GET request for a specific transaction by ID.

    Returns:
        dict: An event dictionary suitable for testing transaction retrieval endpoints.
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
    """
    Pytest fixture that configures the get_transactions app with mocked DynamoDB tables and environment variables for isolated testing.

    Yields:
        The app instance with its transactions table and environment fully mocked for test execution.
    """
    transactions_table_name = mock_transactions_dynamo_table

    monkeypatch.setenv("TRANSACTIONS_TABLE_NAME", transactions_table_name)
    monkeypatch.setenv("ENVIRONMENT_NAME", "test")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "INFO")

    with patch("boto3.resource", return_value=dynamo_resource):
        reload(app)

        app.transactions_table = dynamo_resource.Table(transactions_table_name)

        yield app
