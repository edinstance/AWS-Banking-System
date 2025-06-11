import uuid
from importlib import reload
from unittest.mock import patch, MagicMock

import pytest

from functions.record_transactions.record_transactions import app

VALID_UUID = str(uuid.uuid4())
TEST_USER_ID = str(uuid.uuid4())
TEST_REQUEST_ID = str(uuid.uuid4())
TEST_ID_TOKEN = "dummy.jwt.token"
TEST_USER_POOL_ID = "eu-west-2-testpool"
TEST_CLIENT_ID = "test_client_id"
TEST_AWS_REGION = "eu-west-2"
TEST_SUB = str(uuid.uuid4())
VALID_TRANSACTION_TYPES = ["DEPOSIT", "WITHDRAWAL", "TRANSFER", "ADJUSTMENT"]


@pytest.fixture(scope="function")
def app_with_mocked_table(monkeypatch, dynamo_resource, dynamo_table):
    """
    Provides the app module configured to use a mocked DynamoDB table for testing.

    Sets necessary environment variables and patches AWS resources so that the app module interacts with a mocked DynamoDB table. Yields the reloaded app module with the mocked table assigned for use in tests.
    """
    table_name = dynamo_table
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
    Pytest fixture that provides the app module with no DynamoDB table configured.

    Removes the DynamoDB table environment variable and sets test environment variables before reloading and yielding the app module for tests that require the absence of a table.
    """
    monkeypatch.delenv("TRANSACTIONS_TABLE_NAME", raising=False)
    monkeypatch.setenv("ENVIRONMENT_NAME", "test")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "INFO")

    reload(app)

    yield app


@pytest.fixture
def mock_context():
    """
    Creates a mocked AWS Lambda context object with a preset request ID.

    Returns:
        A MagicMock instance simulating the Lambda context, with the aws_request_id attribute set.
    """
    context = MagicMock()
    context.aws_request_id = TEST_REQUEST_ID
    return context


@pytest.fixture
def valid_event():
    """
    Provides a sample event dictionary representing a valid transaction request.

    The returned event includes headers with an idempotency key and authorisation token, and a JSON body for a deposit transaction.
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
    Yields a mocked DynamoDB table object with an empty query result for testing.

    This fixture patches the application's DynamoDB table so that any query returns an empty list of items, enabling isolated tests without real database access.
    """
    with patch("functions.record_transactions.record_transactions.app.table") as mock:
        mock.query.return_value = {"Items": []}
        yield mock


@pytest.fixture
def mock_auth():
    """
    Pytest fixture that mocks the function extracting the user sub from an ID token.

    Yields:
        The patched mock object for use in tests requiring authentication mocking.
    """
    with patch(
        "functions.record_transactions.record_transactions.auth.get_sub_from_id_token"
    ) as mock:
        mock.return_value = TEST_USER_ID
        yield mock


@pytest.fixture
def mock_jwks_client():
    """
    Pytest fixture that patches the JWKS client used for JWT verification.

    Yields a mock PyJWKClient instance whose `get_signing_key_from_jwt` method returns a mock signing key with a dummy key attribute.
    """
    with patch(
        "functions.record_transactions.record_transactions.auth.PyJWKClient"
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
    Yields a patched mock of the JWT library used in the authentication module for testing purposes.
    """
    with patch(
        "functions.record_transactions.record_transactions.auth.jwt"
    ) as mock_jwt:
        yield mock_jwt


@pytest.fixture
def mock_logger():
    """
    Provides a MagicMock instance to simulate a logger for testing purposes.
    """
    return MagicMock()


@pytest.fixture
def valid_transaction_data():
    """
    Provides a dictionary representing valid transaction data for testing purposes.

    Returns:
        dict: A dictionary containing account ID, amount, transaction type, and description.
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
    Yields a patched mock of the idempotency response creation function for testing.

    This fixture allows tests to intercept and control calls to the `create_response`
    function within the idempotency module of the record_transactions app.
    """
    with patch(
        "functions.record_transactions.record_transactions.idempotency.create_response"
    ) as mock:
        yield mock
