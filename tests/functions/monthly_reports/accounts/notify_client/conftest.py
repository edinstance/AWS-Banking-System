from importlib import reload
from unittest.mock import MagicMock
import pytest
from functions.monthly_reports.accounts.notify_client.notify_client import app


@pytest.fixture(scope="function")
def notify_client_app_with_mocks(
    monkeypatch, mock_s3_client, magic_mock_ses_client, mock_cognito_client
):
    """
    Pytest fixture that prepares and yields the notify-client app with AWS services and environment variables mocked.

    Sets environment variables used by the notify-client Lambda, configures provided mock clients for S3, SES and Cognito with deterministic responses (PDF content, presigned URL, email send results, and Cognito user attributes), reloads the notify_client app module to pick up the environment, injects the mocked S3 client into app.s3, and yields the configured app for tests to use.
    """
    monkeypatch.setenv("SES_NO_REPLY_EMAIL", "noreply@testbank.com")
    monkeypatch.setenv("REPORTS_BUCKET", "test-reports-bucket")
    monkeypatch.setenv("AWS_REGION", "eu-west-2")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "INFO")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "eu-west-2_testpool123")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "test-client-id-123")
    monkeypatch.setenv("DYNAMODB_ENDPOINT", "")
    monkeypatch.setenv("ACCOUNTS_TABLE_NAME", "test-accounts-table")

    mock_s3_client.head_object.return_value = {"ContentLength": 1024 * 1024}  # 1MB
    mock_s3_client.get_object.return_value = {
        "Body": MagicMock(read=lambda: b"%PDF-1.4\n%Test PDF content\n%%EOF")
    }
    mock_s3_client.generate_presigned_url.return_value = "https://test-reports-bucket.s3.eu-west-2.amazonaws.com/test-account-123/2024-01.pdf?AWSAccessKeyId=test&Signature=test&Expires=1234567890"

    magic_mock_ses_client.send_email.return_value = {"MessageId": "test-message-id-123"}
    magic_mock_ses_client.send_raw_email.return_value = {
        "MessageId": "test-message-id-456"
    }

    mock_cognito_client.admin_get_user.return_value = {
        "UserAttributes": [
            {"Name": "email", "Value": "test@example.com"},
            {"Name": "name", "Value": "John Doe"},
        ]
    }

    reload(app)

    app.s3 = mock_s3_client

    yield app


@pytest.fixture
def sample_event():
    """Sample event data for testing."""
    return {
        "accountId": "test-account-123",
        "userId": "test-user-456",
        "statementPeriod": "2024-01",
    }


@pytest.fixture
def mock_context():
    """
    Create and return a MagicMock that simulates an AWS Lambda `context` object for tests.

    The mock provides commonly used attributes:
    - function_name: "notify-client"
    - function_version: "$LATEST"
    - invoked_function_arn: full test ARN for the function
    - memory_limit_in_mb: 128
    - remaining_time_in_millis: callable returning 30000
    - aws_request_id: "test-request-id-123"

    Useful for passing into handler functions that inspect the Lambda context.
    """
    context = MagicMock()
    context.function_name = "notify-client"
    context.function_version = "$LATEST"
    context.invoked_function_arn = (
        "arn:aws:lambda:eu-west-2:123456789012:function:notify-client"
    )
    context.memory_limit_in_mb = 128
    context.remaining_time_in_millis = lambda: 30000
    context.aws_request_id = "test-request-id-123"
    return context


@pytest.fixture
def mock_user_attributes():
    """
    Return a dictionary of mocked Cognito user attributes used in tests.

    Returns:
        dict: Contains `email`, `name` and `sub` keys representing a user's email, full name and Cognito subject id.
    """
    return {"email": "test@example.com", "name": "John Doe", "sub": "test-user-456"}


@pytest.fixture
def mock_pdf_bytes():
    """
    Return a small, mock PDF as bytes for use in tests.

    The bytes represent a minimal PDF file header and footer suitable for tests that only need PDF-like binary content (not a full-featured document).

    Returns:
        bytes: Mock PDF content (starts with `%PDF-1.4` and ends with `%%EOF`).
    """
    return b"%PDF-1.4\n%Test PDF content\n%%EOF"


@pytest.fixture
def mock_presigned_url():
    """
    Return a fixed presigned S3 URL used in tests.

    Returns:
        str: A deterministic presigned URL pointing to the test PDF in the test S3 bucket.
    """
    return "https://test-reports-bucket.s3.eu-west-2.amazonaws.com/test-account-123/2024-01.pdf?AWSAccessKeyId=test&Signature=test&Expires=1234567890"


@pytest.fixture
def mock_dynamodb_table():
    """
    Create a MagicMock representing a DynamoDB table configured for tests.

    The mock's `get_item` method returns a dictionary with an `"Item"` containing sample account data:
    {
        "Item": {
            "accountId": "test-account-123",
            "userId": "test-user-456",
            "balance": 1000.0
        }
    }

    Returns:
        MagicMock: Mocked DynamoDB table with `get_item()` preconfigured to return the sample item.
    """
    mock_table = MagicMock()
    mock_table.get_item.return_value = {
        "Item": {
            "accountId": "test-account-123",
            "userId": "test-user-456",
            "balance": 1000.0,
        }
    }
    return mock_table


@pytest.fixture
def api_gateway_event():
    """
    Return a mock API Gateway proxy event for testing the notify-client Lambda.

    The event simulates an HTTP GET request to the path
    "/accounts/test-account-123/reports/2024-01" and includes headers,
    a requestContext with requestId and HTTP details, and pathParameters
    for `account_id` and `statement_period`. Use this fixture where a
    real API Gateway event shape is required by the handler under test.
    """
    return {
        "httpMethod": "GET",
        "path": "/accounts/test-account-123/reports/2024-01",
        "headers": {
            "Authorization": "Bearer test-jwt-token",
            "Content-Type": "application/json",
        },
        "requestContext": {
            "requestId": "test-request-id-123",
            "http": {
                "method": "GET",
                "path": "/accounts/test-account-123/reports/2024-01",
            },
        },
        "pathParameters": {
            "account_id": "test-account-123",
            "statement_period": "2024-01",
        },
    }
