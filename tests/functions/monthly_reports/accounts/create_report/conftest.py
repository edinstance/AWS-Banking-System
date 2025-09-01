from importlib import reload
from unittest.mock import MagicMock
import pytest
from functions.monthly_reports.accounts.create_report.create_report import app


@pytest.fixture(scope="function")
def create_report_app_with_mocks(monkeypatch, mock_s3_client):
    """Fixture that sets up the create_report app with mocked dependencies."""

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
    """Mock S3 client for testing."""
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
    """Mock PDF bytes for testing."""
    return b"%PDF-1.4\n%Test PDF content\n%%EOF"


@pytest.fixture
def mock_presigned_url():
    """Mock presigned URL for testing."""
    return "https://test-reports-bucket.s3.eu-west-2.amazonaws.com/test-account-123/2024-01.pdf?AWSAccessKeyId=test&Signature=test&Expires=1234567890"
