import uuid
from importlib import reload
from unittest.mock import patch, MagicMock

import pytest

from functions.request_transaction.request_transaction import app

VALID_UUID = str(uuid.uuid4())
TEST_USER_ID = str(uuid.uuid4())
TEST_ID_TOKEN = "dummy.jwt.token"
TEST_USER_POOL_ID = "eu-west-2-testpool"
TEST_CLIENT_ID = "test_client_id"
TEST_AWS_REGION = "eu-west-2"
TEST_SUB = str(uuid.uuid4())
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
    Return a sample event dictionary simulating a valid transaction request.

    The event includes headers with an idempotency key and bearer authorisation token, and a JSON body for a deposit transaction.
    """
    return {
        "headers": {
            "Idempotency-Key": VALID_UUID,
            "Authorization": "Bearer valid-token",
        },
        "body": '{"accountId": "'
        + VALID_UUID
        + '", "amount": "100.50", "type": "DEPOSIT", "description": "Test deposit"}',
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
    Pytest fixture that mocks the extraction of the user ID from an ID token.

    Yields:
        The patched mock object for use in tests that require bypassing actual token decoding.
    """
    with patch(
        "functions.request_transaction.request_transaction.auth.get_sub_from_id_token"
    ) as mock:
        mock.return_value = TEST_USER_ID
        yield mock


@pytest.fixture
def mock_jwks_client():
    """
    Pytest fixture that mocks the JWKS client for JWT verification.

    Yields a patched PyJWKClient whose `get_signing_key_from_jwt` method returns a mock signing key with a dummy key attribute, enabling tests to bypass actual key retrieval.
    """
    with patch(
        "functions.request_transaction.request_transaction.auth.PyJWKClient"
    ) as mock_client:
        mock_instance = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "dummy_key"
        mock_instance.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_client.return_value = mock_instance
        yield mock_client


@pytest.fixture
def mock_jwt():
    """
    Yields a patched mock of the JWT library used in the authentication module for test cases.

    This fixture allows tests to control or inspect JWT operations by providing a mock object in place of the actual JWT library.
    """
    with patch(
        "functions.request_transaction.request_transaction.auth.jwt"
    ) as mock_jwt:
        yield mock_jwt


@pytest.fixture
def valid_transaction_data():
    """
    Return a dictionary with valid transaction data fields for use in tests.

    Returns:
        dict: Contains account ID, amount, transaction type, and description.
    """
    return {
        "accountId": VALID_UUID,
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
