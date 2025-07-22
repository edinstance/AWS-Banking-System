import uuid
from unittest.mock import patch, MagicMock

import pytest
from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

from authentication.authenticate_request import authenticate_request
from tests.layers.authentication.conftest import (
    TEST_USER_POOL_ID,
    TEST_CLIENT_ID,
    TEST_AWS_REGION,
)


class TestAuthenticateRequest:

    def test_auth_error(self, mock_logger, valid_event, headers_with_jwt):
        with patch(
            "authentication.authenticate_request.authenticate_user"
        ) as mock_authenticate_user:
            mock_authenticate_user.return_value = (
                None,
                UnauthorizedError(
                    "Unauthorized: User identity could not be determined"
                ),
            )

            with pytest.raises(UnauthorizedError) as exception_info:
                event = MagicMock()
                event.raw_event = valid_event
                authenticate_request(
                    event,
                    headers_with_jwt["headers"],
                    TEST_USER_POOL_ID,
                    TEST_CLIENT_ID,
                    TEST_AWS_REGION,
                    mock_logger,
                )

            assert exception_info.type == UnauthorizedError
            assert (
                exception_info.value.msg
                == "Unauthorized: User identity could not be determined"
            )

    def test_no_user_id(self, mock_logger, valid_event, headers_with_jwt):
        with patch(
            "authentication.authenticate_request.authenticate_user"
        ) as mock_authenticate_user:
            mock_authenticate_user.return_value = (None, None)

            with pytest.raises(UnauthorizedError) as exception_info:
                event = MagicMock()
                event.raw_event = valid_event
                authenticate_request(
                    event,
                    headers_with_jwt["headers"],
                    TEST_USER_POOL_ID,
                    TEST_CLIENT_ID,
                    TEST_AWS_REGION,
                    mock_logger,
                )

            assert exception_info.type == UnauthorizedError
            assert (
                exception_info.value.msg
                == "Unauthorized: User identity could not be determined"
            )

    def test_success(self, mock_logger, valid_event, headers_with_jwt):
        with patch(
            "authentication.authenticate_request.authenticate_user"
        ) as mock_authenticate_user:
            user_id = str(uuid.uuid4())
            mock_authenticate_user.return_value = (user_id, None)

            event = MagicMock()
            event.raw_event = valid_event

            response = authenticate_request(
                event,
                headers_with_jwt["headers"],
                TEST_USER_POOL_ID,
                TEST_CLIENT_ID,
                TEST_AWS_REGION,
                mock_logger,
            )

            assert response == user_id
