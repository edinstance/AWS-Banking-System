from importlib import reload
from unittest.mock import patch

import pytest

from functions.cognito.post_sign_up.post_sign_up import app


@pytest.fixture(scope="function")
def app_with_mocked_accounts_table(
    monkeypatch, dynamo_resource, mock_accounts_dynamo_table
):
    """
    Yield the app module configured to use a mocked DynamoDB table for testing.

    This fixture sets environment variables and patches AWS resources so that the app module interacts with a mocked DynamoDB table. The reloaded app module has the mocked table assigned and is ready for use in tests.
    """
    table_name = mock_accounts_dynamo_table
    monkeypatch.setenv("ACCOUNTS_TABLE_NAME", table_name)
    monkeypatch.setenv("ENVIRONMENT_NAME", "test")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "INFO")

    with patch("boto3.resource", return_value=dynamo_resource):
        reload(app)

        app.table = dynamo_resource.Table(table_name)

        yield app
