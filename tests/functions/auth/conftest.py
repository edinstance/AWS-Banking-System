from unittest.mock import MagicMock

import pytest

from functions.auth.auth.config import AuthConfig
from functions.auth.auth.service import AuthService
from tests.functions.auth.mock_exceptions import (
    MockUserNotConfirmedException,
    MockNotAuthorizedException,
    MockUserNotFoundException,
    MockTooManyRequestsException,
)


@pytest.fixture
def auth_service_instance(monkeypatch, mock_cognito_user_pool):
    """
    Creates an AuthService instance configured for testing with mocked Cognito settings.

    Environment variables for Cognito client ID, user pool ID, and log level are set using monkeypatch. The returned AuthService uses a mocked Cognito client and a mocked logger, enabling isolated authentication tests.
    """
    monkeypatch.setenv("COGNITO_CLIENT_ID", mock_cognito_user_pool["client_id"])
    monkeypatch.setenv("COGNITO_USER_POOL_ID", mock_cognito_user_pool["user_pool_id"])
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")  # Set default AWS region

    config = AuthConfig()
    service = AuthService(
        config=config, cognito_client=mock_cognito_user_pool["cognito_client"]
    )
    service.logger = MagicMock()
    return service


@pytest.fixture
def auth_service_instance_with_mock_cognito(monkeypatch, mock_cognito_user_pool):
    """
    Creates an AuthService instance with a mocked Cognito client and custom exception classes for testing.

    The returned AuthService is configured with environment variables and a MagicMock Cognito client whose exception attributes are set to custom mock exception classes, enabling simulation of various Cognito error scenarios in tests.
    """
    monkeypatch.setenv("COGNITO_CLIENT_ID", mock_cognito_user_pool["client_id"])
    monkeypatch.setenv("COGNITO_USER_POOL_ID", mock_cognito_user_pool["user_pool_id"])
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")

    mock_cognito_client = MagicMock()
    mock_cognito_client.exceptions.NotAuthorizedException = MockNotAuthorizedException
    mock_cognito_client.exceptions.UserNotConfirmedException = (
        MockUserNotConfirmedException
    )
    mock_cognito_client.exceptions.UserNotFoundException = MockUserNotFoundException
    mock_cognito_client.exceptions.TooManyRequestsException = (
        MockTooManyRequestsException
    )

    config = AuthConfig()
    service = AuthService(config=config, cognito_client=mock_cognito_client)
    service.logger = MagicMock()
    return service
