from unittest.mock import Mock, patch

import pytest

import functions.auth.auth.service
from functions.auth.auth.service import get_auth_service


@pytest.fixture(autouse=True)
def reset_auth_service_singleton():
    functions.auth.auth.service._auth_service = None
    yield
    functions.auth.auth.service._auth_service = None


class TestAuthServiceFactory:

    def test_get_auth_service_creates_new_instance_when_none(self):
        with patch(
            "functions.auth.auth.service.AuthConfig"
        ) as mock_config_class, patch(
            "functions.auth.auth.service.AuthService"
        ) as mock_service_class:
            mock_config = Mock()
            mock_config_class.return_value = mock_config
            mock_service = Mock()
            mock_service_class.return_value = mock_service

            result = get_auth_service()
            result_cached = get_auth_service()

            mock_config_class.assert_called_once()
            mock_service_class.assert_called_once_with(mock_config)

            assert result == mock_service
            assert result_cached is result
