import uuid
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
    Pytest fixture that configures the process_transactions app to use mocked DynamoDB tables for isolated testing.
    
    Sets environment variables and patches AWS resource calls so that the app interacts with provided mock tables. Yields the configured app instance for use in tests.
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


@pytest.fixture
def sample_event_with_records():
    """
    Provide a sample DynamoDB stream event with a single INSERT record for transaction testing.
    
    Returns:
        dict: A dictionary structured as a DynamoDB event, containing one INSERT record with transaction fields such as id, accountId, userId, idempotencyKey, amount, and type.
    """
    return {
        "Records": [
            {
                "eventName": "INSERT",
                "dynamodb": {
                    "SequenceNumber": "12345",
                    "NewImage": {
                        "id": {"S": str(uuid.uuid4())},
                        "accountId": {"S": str(uuid.uuid4())},
                        "userId": {"S": str(uuid.uuid4())},
                        "idempotencyKey": {"S": str(uuid.uuid4())},
                        "amount": {"N": "100.50"},
                        "type": {"S": "DEPOSIT"},
                    },
                },
            }
        ]
    }
