import os
import uuid
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

AWS_REGION = "eu-west-2"
TEST_REQUEST_ID = str(uuid.uuid4())

boto3.setup_default_session(region_name=AWS_REGION)


@pytest.fixture(scope="function")
def aws_credentials():
    """
    Set environment variables with mock AWS credentials and region for testing.

    Ensures AWS SDK clients use fake credentials and the specified region, enabling AWS service simulation with the `moto` library during tests.
    """
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = AWS_REGION
    os.environ["AWS_REGION"] = AWS_REGION


@pytest.fixture(scope="function")
def environment_variables():
    """
    Set environment variables for AWS resource names, endpoints, and logging configuration used during tests.
    """
    os.environ["ACCOUNTS_TABLE_NAME"] = "test-accounts-table"
    os.environ["TRANSACTIONS_TABLE_NAME"] = "test-transactions-table"
    os.environ["TRANSACTION_PROCESSING_DLQ_URL"] = (
        "https://sqs.test.amazonaws.com/123456789012/test-dlq"
    )
    os.environ["SQS_ENDPOINT"] = "https://sqs.test.amazonaws.com"
    os.environ["COGNITO_USER_POOL_ID"] = "test-user-pool"
    os.environ["ENVIRONMENT_NAME"] = "test"
    os.environ["POWERTOOLS_LOG_LEVEL"] = "DEBUG"


@pytest.fixture(scope="function")
def aws_ses_credentials():
    """
    Set environment variables for AWS SES configuration for use in tests.

    This fixture enables SES and specifies sender, reply, and bounce email addresses to simulate SES-related behaviour during testing.
    """
    os.environ["SES_ENABLED"] = "True"
    os.environ["SES_SENDER_EMAIL"] = "sender@example.com"
    os.environ["SES_REPLY_EMAIL"] = "reply@example.com"
    os.environ["SES_BOUNCE_EMAIL"] = "bounce@example.com"


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
def mock_transactions_dynamo_table(dynamo_resource):
    """
    Create a mocked DynamoDB table for transactions with a primary key on 'id' and a global secondary index on 'idempotencyKey'.

    The table is provisioned with 5 read and write capacity units and is synchronously created before returning its name.

    Returns:
        str: The name of the created mocked DynamoDB table.
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
def mock_accounts_dynamo_table(dynamo_resource):
    """
    Create a mocked DynamoDB table named "test-accounts-table" with a primary key on 'accountId' for testing purposes.

    Returns:
        str: The name of the created mocked DynamoDB table.
    """
    table_name = "test-accounts-table"

    # Create the table with just a hash key for 'id'
    table = dynamo_resource.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": "accountId", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "accountId", "AttributeType": "S"},
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
    Yield a mocked AWS Cognito user pool environment for authentication-related testing.

    Creates a Cognito user pool with email auto-verification and a strict password policy, sets up a user pool client with explicit authentication flows, and provisions a test user with a permanent password. Yields a dictionary containing the user pool ID, client ID, username, password, and the Cognito client for use in tests.
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


@pytest.fixture
def mock_ses_client():
    """
    Provides a mocked AWS SES client for use in tests.

    Yields:
        A boto3 SES client configured to use the mocked AWS environment.
    """
    with mock_aws():
        client = boto3.client("ses", region_name=AWS_REGION)

        yield client


@pytest.fixture
def mock_get_ses_client(monkeypatch):
    """
    Pytest fixture that monkeypatches the SES client getter to return a mocked SES client.

    Yields:
        tuple: A tuple containing the mocked SES client getter function and the mocked SES client instance.
    """
    mock_client = MagicMock()
    mock_get_client = MagicMock(return_value=mock_client)
    monkeypatch.setattr("ses.get_ses_client", mock_get_client)

    yield mock_get_client, mock_client


@pytest.fixture
def mock_sqs_client():
    """
    Provide a boto3 SQS client backed by moto for use in tests.

    This fixture yields a boto3 SQS client created inside a moto mock AWS context so all SQS operations are handled by the in-memory moto service. The client is configured to use the module's AWS_REGION.
    """
    with mock_aws():
        client = boto3.client("sqs", region_name=AWS_REGION)

        yield client


@pytest.fixture
def mock_sfn_client():
    """
    Provide a boto3 Step Functions client inside a moto mock AWS context for use in tests.

    This fixture yields a Step Functions client created with boto3 and configured to use the module-level AWS_REGION. The client is created inside a moto mock_aws context, so all Step Functions API calls are intercepted by moto and operate against an in-memory mocked service for the duration of the fixture.
    """
    with mock_aws():
        client = boto3.client("stepfunctions", region_name=AWS_REGION)

        yield client


@pytest.fixture
def magic_mock_ses_client():
    """
    Return a plain MagicMock that represents an AWS SES client for use in tests.

    This fixture-style helper supplies a MagicMock configured to stand in for boto3 SES client calls; it does not make any network calls or interact with AWS. Use it to assert call behaviour and to stub SES responses in unit tests.
    """
    mock_client = MagicMock()
    return mock_client


@pytest.fixture
def mock_s3_client():
    """
    Return a MagicMock that behaves like a boto3 S3 client for use in tests.

    The returned mock can be configured (attributes, return_value, side_effect) to simulate S3 operations.
    """
    mock_client = MagicMock()
    return mock_client


@pytest.fixture
def mock_cognito_client():
    """Mock Cognito client for testing."""
    mock_client = MagicMock()
    return mock_client


@pytest.fixture(scope="function")
def magic_mock_sfn_client():
    """
    Provide a MagicMock that stands in for an AWS Step Functions (SFN) client in tests.

    Useful when tests need a lightweight, configurable mock of the SFN client API rather than a moto-backed or real boto3 client.

    Returns:
        MagicMock: a new MagicMock instance representing the SFN client.
    """
    return MagicMock()


@pytest.fixture
def mock_context():
    """
    Create a mocked AWS Lambda context object with a fixed request ID.

    Returns:
        MagicMock: A mock Lambda context with the aws_request_id attribute set to a test UUID.
    """
    context = MagicMock()
    context.aws_request_id = TEST_REQUEST_ID
    return context


@pytest.fixture
def mock_logger():
    """
    Return a MagicMock instance to simulate a logger for use in tests.
    """
    return MagicMock()


@pytest.fixture
def magic_mock_transactions_table():
    """
    Return a MagicMock instance intended to mock the transactions DynamoDB table in tests.
    """
    return MagicMock()


@pytest.fixture
def magic_mock_accounts_table():
    """
    Return a MagicMock instance intended to simulate the accounts DynamoDB table in tests.
    """
    return MagicMock()
