import os

import boto3
import pytest
from moto import mock_aws

AWS_REGION = "eu-west-2"


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = AWS_REGION


@pytest.fixture(scope="function")
def dynamo_resource(aws_credentials):
    """Create a mocked DynamoDB resource."""
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name=AWS_REGION)
        yield resource

@pytest.fixture(scope="function")
def dynamo_table(dynamo_resource):
    """Create a mocked DynamoDB table that matches your application's expectations."""
    table_name = "test-transactions-table"

    # Create the table with just a hash key for 'id'
    table = dynamo_resource.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "id", "KeyType": "HASH"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "idempotencyKey", "AttributeType": "S"}
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "IdempotencyKeyIndex",
                "KeySchema": [
                    {"AttributeName": "idempotencyKey", "KeyType": "HASH"}
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5
                }
            }
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
    )

    # Wait for the table to be created
    table.meta.client.get_waiter('table_exists').wait(TableName=table_name)

    return table_name
