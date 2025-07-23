import uuid
from importlib import reload
from unittest.mock import patch

import pytest

from functions.accounts.get_accounts.get_accounts import app

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
        "functions.accounts.get_accounts.get_accounts.app.authenticate_request"
    ) as mock:
        mock.return_value = TEST_USER_ID
        yield mock


@pytest.fixture
def valid_get_event():
    """
    Return a dictionary representing a valid HTTP GET event for retrieving all accounts.

    The returned event includes the HTTP method, endpoint path, authorisation header, and a unique request ID in the request context.
    """
    return {
        "httpMethod": "GET",
        "path": "/accounts",
        "headers": {
            "Authorization": "Bearer valid-token",
        },
        "requestContext": {
            "requestId": str(uuid.uuid4()),
        },
    }


@pytest.fixture
def valid_get_account_event():
    """
    Generate a sample event dictionary representing a valid HTTP GET request for a specific account by ID.

    Returns:
        dict: An event dictionary suitable for testing account retrieval endpoints.
    """
    account_id = VALID_UUID
    return {
        "httpMethod": "GET",
        "path": f"/accounts/{account_id}",
        "pathParameters": {"account_id": account_id},
        "headers": {
            "Authorization": "Bearer valid-token",
        },
        "requestContext": {
            "requestId": str(uuid.uuid4()),
        },
    }


@pytest.fixture(scope="function")
def get_accounts_app_with_mocked_tables(
    monkeypatch,
    dynamo_resource,
    mock_accounts_dynamo_table,
):
    """
    Pytest fixture that configures the get_accounts app with mocked DynamoDB tables and environment variables for isolated testing.

    Yields:
        The app instance with its accounts table and environment fully mocked for test execution.
    """
    accounts_table_name = mock_accounts_dynamo_table

    monkeypatch.setenv("ACCOUNTS_TABLE_NAME", accounts_table_name)
    monkeypatch.setenv("ENVIRONMENT_NAME", "test")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "INFO")

    with patch("boto3.resource", return_value=dynamo_resource):
        reload(app)

        app.accounts_table = dynamo_resource.Table(accounts_table_name)

        yield app
