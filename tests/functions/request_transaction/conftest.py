import uuid
from importlib import reload
from unittest.mock import patch

import pytest

from functions.request_transaction.request_transaction import app

# Constants needed by other test modules
VALID_UUID = str(uuid.uuid4())
TEST_SUB = str(uuid.uuid4())
TEST_ID_TOKEN = "dummy.jwt.token"
VALID_TRANSACTION_TYPES = ["DEPOSIT", "WITHDRAWAL", "TRANSFER", "ADJUSTMENT"]


@pytest.fixture(scope="function")
def app_with_mocked_table(monkeypatch, dynamo_resource, mock_transactions_dynamo_table):
    """
    Yield the app module configured to use a mocked DynamoDB table for testing.

    Sets environment variables and patches AWS resources so that the app interacts with a mocked DynamoDB table, enabling isolated and repeatable tests.
    """
    table_name = mock_transactions_dynamo_table
    monkeypatch.setenv("TRANSACTIONS_TABLE_NAME", table_name)
    monkeypatch.setenv("ENVIRONMENT_NAME", "test")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "INFO")

    with patch("boto3.resource", return_value=dynamo_resource):
        reload(app)

        app.table = dynamo_resource.Table(table_name)

        yield app


@pytest.fixture(scope="function")
def app_without_table(monkeypatch):
    """
    Pytest fixture that yields the app module with DynamoDB table configuration removed.

    Removes the DynamoDB table environment variable and sets test environment variables, then reloads and yields the app module for tests simulating the absence of a table.
    """
    monkeypatch.delenv("TRANSACTIONS_TABLE_NAME", raising=False)
    monkeypatch.setenv("ENVIRONMENT_NAME", "test")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "INFO")

    reload(app)

    yield app


@pytest.fixture
def valid_event():
    """
    Return a dictionary representing a valid HTTP POST event for a transaction request.
    
    The event includes dynamically generated idempotency key, account ID, and request ID, along with headers and a JSON body for a deposit transaction.
    """
    return {
        "httpMethod": "POST",
        "path": "/transactions",
        "headers": {
            "Idempotency-Key": str(uuid.uuid4()),
            "Authorization": "Bearer valid-token",
        },
        "body": '{"accountId": "'
        + str(uuid.uuid4())
        + '", "amount": "100.50", "type": "DEPOSIT", "description": "Test deposit"}',
        "requestContext": {
            "requestId": str(uuid.uuid4()),
        },
    }


@pytest.fixture
def headers_with_jwt():
    """
    Provides headers containing a bearer JWT token for use in authentication tests.

    Returns:
        A dictionary with an 'authorization' header set to a bearer token.
    """
    return {
        "headers": {
            "authorization": "Bearer valid-token",
        }
    }


@pytest.fixture
def empty_headers():
    """
    Provides a dictionary with empty headers for use in tests.
    """
    return {"headers": {}}


@pytest.fixture
def mock_table():
    """
    Fixture that yields a mocked DynamoDB table with empty results for get_item and query operations.

    Simulates an empty database state by ensuring get_item returns {"Item": None} and query returns {"Items": []}.
    """
    with patch("functions.request_transaction.request_transaction.app.table") as mock:
        mock.query.return_value = {"Items": []}
        mock.get_item.return_value = {"Item": None}
        yield mock


@pytest.fixture
def mock_auth():
    """
    Pytest fixture that patches the app's authentication function to always return a random UUID.
    
    Yields:
        The patched mock object, allowing tests to bypass real authentication and control the returned user identifier.
    """
    with patch(
        "functions.request_transaction.request_transaction.app.authenticate_request"
    ) as mock:
        mock.return_value = str(uuid.uuid4())
        yield mock


@pytest.fixture
def valid_transaction_data():
    """
    Generate a dictionary containing valid transaction data for testing.
    
    Returns:
        dict: A dictionary with dynamically generated account ID, amount, transaction type, and description fields.
    """
    return {
        "accountId": str(uuid.uuid4()),
        "amount": "100.50",
        "type": "DEPOSIT",
        "description": "Test transaction",
    }


@pytest.fixture
def mock_create_response():
    """
    Yields a patched mock of the `create_response` function from the idempotency module for use in tests.

    This fixture enables tests to intercept and control idempotency response creation within the request_transaction app.
    """
    with patch(
        "functions.request_transaction.request_transaction.idempotency.create_response"
    ) as mock:
        yield mock
