from importlib import reload
from unittest.mock import patch

import pytest


@pytest.fixture(scope="function")
def app_with_mocked_table(monkeypatch, dynamo_resource, dynamo_table):
    """
    Pytest fixture that provides the app module with a mocked DynamoDB table.
    
    Sets environment variables and patches AWS resources so that the app module uses
    a mocked DynamoDB table for isolated testing. Yields the reloaded app module
    with the mocked table assigned.
    """
    # First, set the environment variable
    table_name = dynamo_table
    monkeypatch.setenv("TRANSACTIONS_TABLE_NAME", table_name)
    monkeypatch.setenv("ENVIRONMENT_NAME", "test")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "INFO")

    # Patch boto3.resource to return our mocked resource
    with patch('boto3.resource', return_value=dynamo_resource):
        # Now import and reload the app
        from functions.record_transactions import app
        reload(app)

        # Make sure the table is properly set
        app.table = dynamo_resource.Table(table_name)

        yield app


@pytest.fixture(scope="function")
def app_without_table(monkeypatch):
    """
    Pytest fixture that reloads the app module without a configured DynamoDB table.
    
    Removes the TRANSACTIONS_TABLE_NAME environment variable and sets test-specific
    environment variables before reloading and yielding the app module.
    """
    # Remove the environment variable
    monkeypatch.delenv("TRANSACTIONS_TABLE_NAME", raising=False)
    monkeypatch.setenv("ENVIRONMENT_NAME", "test")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "INFO")

    # Now import and reload the app
    from functions.record_transactions import app
    reload(app)

    yield app
