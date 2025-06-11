import os

import boto3
import pytest
from moto import mock_aws

AWS_REGION = "eu-west-2"

boto3.setup_default_session(region_name=AWS_REGION)


@pytest.fixture(scope="function")
def aws_credentials():
    """
    Sets environment variables with fake AWS credentials and region for test environments.
    
    Configures the environment so that AWS SDK clients operate with mock credentials, allowing AWS services to be simulated using the `moto` library during testing.
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
    
    The table is provisioned with 5 read and write capacity units and is synchronously created before returning its name.
    
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


@pytest.fixture(scope="function")
def cognito_client():
    """
    Provides a mocked AWS Cognito Identity Provider client for testing.
    
    Yields:
        A boto3 Cognito Identity Provider client configured for the mocked AWS environment.
    """
    with mock_aws():
        client = boto3.client("cognito-idp", region_name=AWS_REGION)
        yield client


@pytest.fixture(scope="function")
def mock_cognito_user_pool(cognito_client):
    """
    Provides a mocked Cognito user pool environment for testing.
    
    Creates a Cognito user pool with email auto-verification and a strict password policy, sets up a user pool client with explicit authentication flows, and creates a test user with a permanent password. Yields a dictionary containing the user pool ID, client ID, username, password, and the Cognito client for use in tests.
    """
    user_pool_name = "test-user-pool"
    client_name = "test-app-client"
    test_username = "test_user"
    test_password = "Password123!"

    user_pool_response = cognito_client.create_user_pool(
        PoolName=user_pool_name,
        AutoVerifiedAttributes=["email"],
        Policies={
            "PasswordPolicy": {
                "MinimumLength": 8,
                "RequireUppercase": True,
                "RequireLowercase": True,
                "RequireNumbers": True,
                "RequireSymbols": True,
            }
        },
    )
    user_pool_id = user_pool_response["UserPool"]["Id"]

    client_response = cognito_client.create_user_pool_client(
        UserPoolId=user_pool_id,
        ClientName=client_name,
        ExplicitAuthFlows=[
            "ADMIN_USER_PASSWORD_AUTH",
            "REFRESH_TOKEN_AUTH",
        ],
    )
    client_id = client_response["UserPoolClient"]["ClientId"]

    cognito_client.admin_create_user(
        UserPoolId=user_pool_id,
        Username=test_username,
        UserAttributes=[
            {"Name": "email", "Value": "testuser@example.com"},
        ],
        TemporaryPassword=test_password,
        MessageAction="SUPPRESS",
    )

    cognito_client.admin_set_user_password(
        UserPoolId=user_pool_id,
        Username=test_username,
        Password=test_password,
        Permanent=True,
    )

    yield {
        "user_pool_id": user_pool_id,
        "client_id": client_id,
        "username": test_username,
        "password": test_password,
        "cognito_client": cognito_client,
    }
