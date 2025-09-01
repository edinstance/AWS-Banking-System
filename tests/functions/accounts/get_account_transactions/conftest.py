import uuid
from importlib import reload
from unittest.mock import patch

import pytest

from functions.accounts.get_account_transactions.get_account_transactions import app

VALID_UUID = str(uuid.uuid4())


@pytest.fixture
def valid_get_transactions_event():
    """
    Return a dictionary representing a valid HTTP GET event for retrieving account transactions.

    The returned event includes the HTTP method, endpoint path, authorisation header, and a unique request ID in the request context.
    """
    account_id = VALID_UUID
    return {
        "httpMethod": "GET",
        "path": f"/accounts/{account_id}/transactions",
        "pathParameters": {"account_id": account_id},
        "headers": {
            "Authorization": "Bearer valid-token",
        },
        "requestContext": {
            "requestId": str(uuid.uuid4()),
        },
    }


@pytest.fixture
def step_functions_event():
    """
    Return a dictionary representing a Step Functions event for retrieving account transactions.

    The returned event includes the accountId field that Step Functions would pass.
    """
    return {
        "accountId": VALID_UUID,
        "someOtherData": "value",
    }


@pytest.fixture(scope="function")
def get_account_transactions_app_with_mocked_tables(
    monkeypatch,
    dynamo_resource,
    mock_transactions_dynamo_table,
):
    """
    Fixture that prepares the get_account_transactions application for isolated tests.

    Sets environment variables required by the application, patches boto3.resource to use the provided mocked DynamoDB resource, reloads the application module so it picks up the patched resource, assigns the mocked transactions table to app.table and yields the configured app instance for test use.
    """
    transactions_table_name = mock_transactions_dynamo_table

    monkeypatch.setenv("TRANSACTIONS_TABLE_NAME", transactions_table_name)
    monkeypatch.setenv("ENVIRONMENT_NAME", "test")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "INFO")
    monkeypatch.setenv("AWS_REGION", "eu-west-2")

    with patch("boto3.resource", return_value=dynamo_resource):
        reload(app)

        app.table = dynamo_resource.Table(transactions_table_name)

        yield app
