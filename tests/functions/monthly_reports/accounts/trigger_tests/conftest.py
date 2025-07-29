from importlib import reload
from functions.monthly_reports.accounts.trigger.trigger import app
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(scope="function")
def magic_mock_sfn_client():
    return MagicMock()


@pytest.fixture(scope="function")
def monthly_accounts_reports_app_with_mocks(
    monkeypatch, dynamo_resource, mock_accounts_dynamo_table
):
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

    with patch("boto3.resource", return_value=dynamo_resource):
        reload(app)

        app.accounts_table = dynamo_resource.Table(accounts_table_name)

        yield app
