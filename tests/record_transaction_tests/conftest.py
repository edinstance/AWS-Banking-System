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
    Pytest fixture that provides the app module with a mocked DynamoDB table.

    Sets environment variables and patches AWS resources so that the app module uses
    a provided mocked DynamoDB table for testing. The fixture yields the reloaded
    app module with the mocked table assigned.
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
    Pytest fixture that reloads the app module without a configured DynamoDB table.

    Removes the TRANSACTIONS_TABLE_NAME environment variable and sets test-specific
    environment variables before reloading and yielding the app module for use in tests.
    """
    monkeypatch.delenv("TRANSACTIONS_TABLE_NAME", raising=False)
    monkeypatch.setenv("ENVIRONMENT_NAME", "test")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "INFO")

    reload(app)

    yield app


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.aws_request_id = TEST_REQUEST_ID
    return context


@pytest.fixture
def valid_event():
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
    return {
        "headers": {
            "authorization": "Bearer valid-token",
        }
    }


@pytest.fixture
def empty_headers():
    return {"headers": {}}


@pytest.fixture
def mock_table():
    with patch("functions.record_transactions.record_transactions.app.table") as mock:
        mock.query.return_value = {"Items": []}
        yield mock


@pytest.fixture
def mock_auth():
    with patch(
        "functions.record_transactions.record_transactions.auth.get_sub_from_id_token"
    ) as mock:
        mock.return_value = TEST_USER_ID
        yield mock


@pytest.fixture
def mock_jwks_client():
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
    with patch(
        "functions.record_transactions.record_transactions.auth.jwt"
    ) as mock_jwt:
        yield mock_jwt


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def valid_transaction_data():
    return {
        "accountId": VALID_UUID,
        "amount": "100.50",
        "type": "DEPOSIT",
        "description": "Test transaction",
    }


@pytest.fixture
def mock_create_response():
    with patch(
        "functions.record_transactions.record_transactions.idempotency.create_response"
    ) as mock:
        yield mock
