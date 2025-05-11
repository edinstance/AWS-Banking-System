import os

import boto3
import pytest
from moto import mock_aws

AWS_REGION = "eu-west-2"

boto3.setup_default_session(region_name=AWS_REGION)


@pytest.fixture(scope="function")
def aws_credentials():
    """
    Sets environment variables to provide dummy AWS credentials and region for testing.

    This fixture configures the environment so that AWS SDK clients use mock credentials,
    enabling the use of the `moto` library to simulate AWS services during tests.
    """
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = AWS_REGION


@pytest.fixture(scope="function")
def dynamo_resource(aws_credentials):
    """
    Provides a mocked DynamoDB resource for use in tests.

    Yields:
        A boto3 DynamoDB resource object configured for the mocked AWS environment.
    """
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name=AWS_REGION)
        yield resource


@pytest.fixture(scope="function")
def dynamo_table(dynamo_resource):
    """
    Creates a mocked DynamoDB table with a primary key on 'id' and a global secondary index on 'idempotencyKey'.

    The table is provisioned with read and write capacity units of 5 and is synchronously created before returning its name.

    Returns:
        The name of the created mocked DynamoDB table.
    """
    table_name = "test-transactions-table"

    # Create the table with just a hash key for 'id'
    table = dynamo_resource.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "idempotencyKey", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "IdempotencyKeyIndex",
                "KeySchema": [{"AttributeName": "idempotencyKey", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            }
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )

    # Wait for the table to be created
    table.meta.client.get_waiter("table_exists").wait(TableName=table_name)

    return table_name
