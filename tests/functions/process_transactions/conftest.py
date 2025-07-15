from importlib import reload
from unittest.mock import patch

import pytest

from functions.process_transactions.process_transactions import app


@pytest.fixture(scope="function")
def process_app_with_mocked_tables(
    monkeypatch,
    dynamo_resource,
    mock_transactions_dynamo_table,
    mock_accounts_dynamo_table,
):
    """
    Pytest fixture that configures the process_transactions app with mocked DynamoDB tables for testing.

    Sets environment variables and patches AWS resource calls to use provided mock tables, then yields the configured app instance for use in tests.
    """
    transactions_table_name = mock_transactions_dynamo_table
    accounts_table_name = mock_accounts_dynamo_table

    monkeypatch.setenv("TRANSACTIONS_TABLE_NAME", transactions_table_name)
    monkeypatch.setenv("ACCOUNTS_TABLE_NAME", accounts_table_name)
    monkeypatch.setenv("ENVIRONMENT_NAME", "test")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "INFO")

    with patch("boto3.resource", return_value=dynamo_resource):
        reload(app)

        app.transactions_table = dynamo_resource.Table(transactions_table_name)
        app.accounts_table = dynamo_resource.Table(accounts_table_name)

        yield app
