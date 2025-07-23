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
    Pytest fixture that patches the JWKS client to return a mock signing key for JWT verification.
    
    Yields:
        The patched PyJWKClient class, configured so that `get_signing_key_from_jwt` returns a mock object with a dummy key attribute. This allows tests to bypass real JWKS key retrieval.
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
    Yields a patched mock of the JWT library for use in authentication-related tests.
    
    This fixture enables tests to substitute the real JWT library with a mock, allowing control and inspection of JWT operations during test execution.
    """
    with patch("authentication.id_extraction.jwt") as mock_jwt:
        yield mock_jwt


@pytest.fixture
def valid_event():
    """
    Return a dictionary representing a valid HTTP POST event for a deposit transaction.
    
    The event includes headers with an idempotency key and bearer authorisation token, a JSON body specifying transaction details, and a request context with a unique request ID.
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
    Return a dictionary containing HTTP headers with a bearer JWT token for authentication testing.
    
    Returns:
        dict: A dictionary with an 'authorization' header set to 'Bearer valid-token'.
    """
    return {
        "headers": {
            "authorization": "Bearer valid-token",
        }
    }


@pytest.fixture
def empty_headers():
    """
    Return a dictionary containing empty HTTP headers for use in tests.
    """
    return {"headers": {}}
