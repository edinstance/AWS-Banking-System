from importlib import reload
from functions.monthly_reports.accounts.trigger.trigger import app
from unittest.mock import patch

import pytest


@pytest.fixture(scope="function")
def monthly_accounts_reports_app_with_mocks(
    monkeypatch, dynamo_resource, mock_accounts_dynamo_table
):
    """
    Pytest fixture that provides the monthly accounts reports application configured with mocked AWS resources and environment.
    
    Sets environment variables required by the app (accounts table name, SQS URLs, state machine ARN, environment name, log level, AWS region and DLQ URL), patches boto3.resource to return the provided mocked DynamoDB resource, reloads the application module so the environment and patch take effect, attaches the mocked DynamoDB Table to app.accounts_table, and yields the configured app instance for use in tests.
    """
    accounts_table_name = mock_accounts_dynamo_table

    monkeypatch.setenv("ACCOUNTS_TABLE_NAME", accounts_table_name)
    monkeypatch.setenv(
        "CONTINUATION_QUEUE_URL",
        "https://sqs.eu-west-2.amazonaws.com/123456789012/continuation-queue",
    )
    monkeypatch.setenv("STATE_MACHINE_ARN", "mock_arn")
    monkeypatch.setenv("ENVIRONMENT_NAME", "test")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "INFO")
    monkeypatch.setenv("AWS_REGION", "eu-west-2")
    monkeypatch.setenv(
        "DLQ_URL", "https://sqs.eu-west-2.amazonaws.com/123456789012/dlq"
    )
    monkeypatch.setenv("SQS_ENDPOINT", "https://sqs.eu-west-2.amazonaws.com")

    with patch("boto3.resource", return_value=dynamo_resource):
        reload(app)

        app.accounts_table = dynamo_resource.Table(accounts_table_name)

        yield app
