from importlib import reload
from unittest.mock import MagicMock
import pytest
from functions.monthly_reports.accounts.create_report.create_report import app


@pytest.fixture(scope="function")
def create_report_app_with_mocks(monkeypatch, mock_s3_client):
    """
    Pytest fixture that configures and yields the create_report app module with mocked AWS interactions.

    Sets test environment variables (REPORTS_BUCKET, POWERTOOLS_LOG_LEVEL, AWS_REGION), configures the provided mock S3 client to return a successful put_object response and a fixed presigned URL, reloads the app module, and injects the mock S3 client as app.s3. Yields the prepared app module for use in tests.
    """

    # Set environment variables
    monkeypatch.setenv("REPORTS_BUCKET", "test-reports-bucket")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "INFO")
    monkeypatch.setenv("AWS_REGION", "eu-west-2")

    # Mock the S3 client methods
    mock_s3_client.put_object.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    mock_s3_client.generate_presigned_url.return_value = "https://test-reports-bucket.s3.eu-west-2.amazonaws.com/test-account-123/2024-01.pdf?AWSAccessKeyId=test&Signature=test&Expires=1234567890"

    # Load the app module
    reload(app)

    # Replace the S3 client in the app module directly
    app.s3 = mock_s3_client

    yield app


@pytest.fixture
def mock_s3_client():
    """
    Create and return a fresh MagicMock configured to stand in for an AWS S3 client in tests.

    The mock is unconfigured by default; tests can set expected return values or assertions on calls (e.g. `put_object`, `generate_presigned_url`).
    Returns:
        MagicMock: A new mock object representing the S3 client.
    """
    mock_client = MagicMock()
    return mock_client


@pytest.fixture
def sample_event():
    """Sample event data for testing."""
    return {
        "accountId": "test-account-123",
        "userId": "test-user-456",
        "statementPeriod": "2024-01",
        "transactions": [
            {
                "id": "txn-1",
                "amount": 100.00,
                "description": "Test transaction 1",
                "date": "2024-01-15",
            },
            {
                "id": "txn-2",
                "amount": -50.00,
                "description": "Test transaction 2",
                "date": "2024-01-20",
            },
        ],
        "accountBalance": 1500.00,
    }


@pytest.fixture
def mock_pdf_bytes():
    """
    Return minimal mock PDF bytes for use in tests.

    Provides a small, deterministic PDF binary (bytes) that can be used as placeholder content for upload, storage or processing tests.
    Returns:
        bytes: Minimal PDF binary suitable for unit tests (starts with `%PDF-1.4` and ends with `%%EOF`).
    """
    return b"%PDF-1.4\n%Test PDF content\n%%EOF"


@pytest.fixture
def mock_presigned_url():
    """
    Return a fixed S3 presigned URL used by tests.

    This deterministic URL simulates a presigned S3 object URL (including query parameters)
    so tests can assert URL handling and downstream behaviour without calling AWS.

    Returns:
        str: A mock presigned URL.
    """
    return "https://test-reports-bucket.s3.eu-west-2.amazonaws.com/test-account-123/2024-01.pdf?AWSAccessKeyId=test&Signature=test&Expires=1234567890"
