from unittest.mock import MagicMock

import pytest

from functions.auth.auth.config import AuthConfig
from functions.auth.auth.service import AuthService
from tests.auth.mock_exceptions import (
    MockUserNotConfirmedException,
    MockNotAuthorizedException,
    MockUserNotFoundException,
    MockTooManyRequestsException,
)


@pytest.fixture
def auth_service_instance(monkeypatch, mock_cognito_user_pool):
    monkeypatch.setenv("COGNITO_CLIENT_ID", mock_cognito_user_pool["client_id"])
    monkeypatch.setenv("COGNITO_USER_POOL_ID", mock_cognito_user_pool["user_pool_id"])
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "DEBUG")

    config = AuthConfig()
    service = AuthService(
        config=config, cognito_client=mock_cognito_user_pool["cognito_client"]
    )
    service.logger = MagicMock()
    return service


@pytest.fixture
def auth_service_instance_with_mock_cognito(monkeypatch, mock_cognito_user_pool):
    monkeypatch.setenv("COGNITO_CLIENT_ID", mock_cognito_user_pool["client_id"])
    monkeypatch.setenv("COGNITO_USER_POOL_ID", mock_cognito_user_pool["user_pool_id"])
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "DEBUG")

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
