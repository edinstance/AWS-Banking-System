import uuid
from unittest.mock import patch, MagicMock

import pytest

VALID_UUID = str(uuid.uuid4())
TEST_USER_ID = str(uuid.uuid4())
TEST_ID_TOKEN = "dummy.jwt.token"
TEST_USER_POOL_ID = "eu-west-2-testpool"
TEST_CLIENT_ID = "test_client_id"
TEST_AWS_REGION = "eu-west-2"
TEST_SUB = str(uuid.uuid4())
VALID_TRANSACTION_TYPES = ["DEPOSIT", "WITHDRAWAL", "TRANSFER", "ADJUSTMENT"]


@pytest.fixture
def mock_jwks_client():
    """
    Pytest fixture that mocks the JWKS client for JWT verification.

    Yields a patched PyJWKClient whose `get_signing_key_from_jwt` method returns a mock signing key with a dummy key attribute, enabling tests to bypass actual key retrieval.
    """
    with patch("authentication.id_extraction.PyJWKClient") as mock_client:
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
    with patch("authentication.id_extraction.jwt") as mock_jwt:
        yield mock_jwt


@pytest.fixture
def valid_event():
    """
    Return a sample event dictionary simulating a valid transaction request.

    The event includes headers with an idempotency key and bearer authorisation token, and a JSON body for a deposit transaction.
    """
    return {
        "headers": {
            "Idempotency-Key": str(uuid.uuid4()),
            "Authorization": "Bearer valid-token",
        },
        "body": '{"accountId": "'
        + str(uuid.uuid4())
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
