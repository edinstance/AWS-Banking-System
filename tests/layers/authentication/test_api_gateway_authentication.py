import uuid
from unittest.mock import patch

from aws_lambda_powertools.event_handler.exceptions import (
    UnauthorizedError,
    InternalServerError,
)
from authentication.api_gateway_authentication import authenticate_user
from authentication.exceptions import (
    MissingSubClaimError,
    InvalidTokenError,
    AuthConfigurationError,
    AuthVerificationError,
)
from tests.layers.authentication.conftest import (
    TEST_USER_POOL_ID,
    TEST_CLIENT_ID,
    TEST_AWS_REGION,
)


def test_authenticate_user_success(valid_event, headers_with_jwt, mock_logger):
    with patch(
        "authentication.api_gateway_authentication.get_sub_from_id_token"
    ) as mock_get_sub_from_id_token:

        mock_get_sub_from_id_token.return_value = str(uuid.uuid4())

        user_id, response = authenticate_user(
            valid_event,
            headers_with_jwt["headers"],
            TEST_USER_POOL_ID,
            TEST_CLIENT_ID,
            TEST_AWS_REGION,
            mock_logger,
        )

        assert user_id


def test_authenticate_user_missing_authorization(
    valid_event, empty_headers, mock_logger
):
    """
    Tests that authenticate_user returns a 401 response when the Authorization header is missing.

    Removes the "Authorization" header from the event and verifies that the function returns None for the user ID and a 401 response with an appropriate error message.
    """
    valid_event["headers"].pop("Authorization")

    user_id, response = authenticate_user(
        valid_event,
        empty_headers,
        TEST_USER_POOL_ID,
        TEST_CLIENT_ID,
        TEST_AWS_REGION,
        mock_logger,
    )

    assert user_id is None
    assert isinstance(response, UnauthorizedError)
    assert (
        "Unauthorized: User identity could not be determined. Please ensure a valid token is provided."
        in str(response)
    )


def test_authenticate_user_invalid_token(valid_event, headers_with_jwt, mock_logger):
    """
    Tests that authenticate_user returns a 401 response with an appropriate error message when an invalid authentication token is provided.
    """
    with patch(
        "authentication.api_gateway_authentication.get_sub_from_id_token"
    ) as mock_get_sub_from_id_token:

        mock_get_sub_from_id_token.side_effect = InvalidTokenError(
            "Signature verification failed"
        )

        user_id, response = authenticate_user(
            valid_event,
            headers_with_jwt["headers"],
            TEST_USER_POOL_ID,
            TEST_CLIENT_ID,
            TEST_AWS_REGION,
            mock_logger,
        )

        assert user_id is None
        assert isinstance(response, UnauthorizedError)
        assert (
            str(response)
            == "Unauthorized: Invalid authentication token (Signature verification failed)"
        )


def test_authenticate_user_missing_sub_claim(
    valid_event, headers_with_jwt, mock_logger
):
    """
    Tests that authenticate_user returns a 401 response with an appropriate error message when the ID token is missing the 'sub' claim.
    """

    with patch(
        "authentication.api_gateway_authentication.get_sub_from_id_token"
    ) as mock_get_sub_from_id_token:

        mock_get_sub_from_id_token.side_effect = MissingSubClaimError(
            "Missing sub claim"
        )

        user_id, response = authenticate_user(
            valid_event,
            headers_with_jwt["headers"],
            TEST_USER_POOL_ID,
            TEST_CLIENT_ID,
            TEST_AWS_REGION,
            mock_logger,
        )

        assert user_id is None
        assert isinstance(response, UnauthorizedError)
        assert (
            str(response)
            == "Unauthorized: Invalid authentication token (Missing sub claim)"
        )


def test_authenticate_user_auth_configuration_error(
    valid_event, headers_with_jwt, mock_logger
):
    """
    Tests that authenticate_user returns a 500 response with an appropriate error message when an AuthConfigurationError is raised during authentication.
    """

    with patch(
        "authentication.api_gateway_authentication.get_sub_from_id_token"
    ) as mock_get_sub_from_id_token:

        mock_get_sub_from_id_token.side_effect = AuthConfigurationError("Config error")

        user_id, response = authenticate_user(
            valid_event,
            headers_with_jwt["headers"],
            TEST_USER_POOL_ID,
            TEST_CLIENT_ID,
            TEST_AWS_REGION,
            mock_logger,
        )

        assert isinstance(response, InternalServerError)
        assert "Server authentication configuration error" in str(response)


def test_authenticate_user_verification_error(
    valid_event, headers_with_jwt, mock_logger
):
    """
    Tests that authenticate_user returns a 500 response with an internal authentication error message when AuthVerificationError is raised during token verification.
    """

    with patch(
        "authentication.api_gateway_authentication.get_sub_from_id_token"
    ) as mock_get_sub_from_id_token:

        mock_get_sub_from_id_token.side_effect = AuthVerificationError(
            "Verification error"
        )

        user_id, response = authenticate_user(
            valid_event,
            headers_with_jwt["headers"],
            TEST_USER_POOL_ID,
            TEST_CLIENT_ID,
            TEST_AWS_REGION,
            mock_logger,
        )

        assert isinstance(response, InternalServerError)
        assert "Internal authentication error" in str(response)


def test_authenticate_user_unexpected_error(valid_event, headers_with_jwt, mock_logger):
    """
    Tests that authenticate_user returns a 500 response with an appropriate error message when an unexpected exception is raised during authentication.
    """
    with patch(
        "authentication.api_gateway_authentication.get_sub_from_id_token"
    ) as mock_get_sub_from_id_token:

        mock_get_sub_from_id_token.side_effect = Exception("Unknown error")

        user_id, response = authenticate_user(
            valid_event,
            headers_with_jwt["headers"],
            TEST_USER_POOL_ID,
            TEST_CLIENT_ID,
            TEST_AWS_REGION,
            mock_logger,
        )

        assert isinstance(response, InternalServerError)
        assert "An unexpected error occurred during authentication." in str(response)
