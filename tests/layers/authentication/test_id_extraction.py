from unittest.mock import MagicMock

import pytest
from jwt.exceptions import (
    PyJWTError,
    InvalidAudienceError,
    InvalidIssuerError,
    ExpiredSignatureError,
)

from authentication.exceptions import (
    MissingSubClaimError,
    InvalidTokenError,
    AuthConfigurationError,
    AuthVerificationError,
)
from authentication.id_extraction import get_sub_from_id_token
from tests.layers.authentication.conftest import (
    TEST_SUB,
    TEST_ID_TOKEN,
    TEST_USER_POOL_ID,
    TEST_CLIENT_ID,
    TEST_AWS_REGION,
)


def test_successful_token_verification(mock_jwks_client, mock_jwt):
    mock_jwt.decode.return_value = {"token_use": "id", "sub": TEST_SUB}
    mock_logger = MagicMock()

    result = get_sub_from_id_token(
        TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION, mock_logger
    )

    assert result == TEST_SUB
    mock_jwt.decode.assert_called_once_with(
        TEST_ID_TOKEN,
        "dummy_key",
        algorithms=["RS256"],
        audience=TEST_CLIENT_ID,
        issuer=f"https://cognito-idp.{TEST_AWS_REGION}.amazonaws.com/{TEST_USER_POOL_ID}",
    )


def test_missing_sub_claim(mock_jwks_client, mock_jwt):
    """
    Tests that get_sub_from_id_token raises MissingSubClaimError when the ID token payload lacks the 'sub' claim.
    """
    mock_jwt.decode.return_value = {"token_use": "id"}
    mock_logger = MagicMock()

    with pytest.raises(MissingSubClaimError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN,
            TEST_USER_POOL_ID,
            TEST_CLIENT_ID,
            TEST_AWS_REGION,
            mock_logger,
        )
    assert "missing the 'sub' claim" in str(exc_info.value)


def test_invalid_token_use(mock_jwks_client, mock_jwt):
    """
    Tests that get_sub_from_id_token raises InvalidTokenError when the token's 'token_use' claim is not 'id'.
    """
    mock_jwt.decode.return_value = {"token_use": "access", "sub": TEST_SUB}
    mock_logger = MagicMock()

    with pytest.raises(InvalidTokenError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN,
            TEST_USER_POOL_ID,
            TEST_CLIENT_ID,
            TEST_AWS_REGION,
            mock_logger,
        )
    assert "Token is not an ID token" in str(exc_info.value)


def test_invalid_audience(mock_jwks_client, mock_jwt):
    """
    Tests that get_sub_from_id_token raises InvalidTokenError when the token audience is invalid.
    """
    mock_jwt.decode.side_effect = InvalidAudienceError("Invalid audience")
    mock_logger = MagicMock()

    with pytest.raises(InvalidTokenError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN,
            TEST_USER_POOL_ID,
            TEST_CLIENT_ID,
            TEST_AWS_REGION,
            mock_logger,
        )
    assert "Invalid audience" in str(exc_info.value)


def test_invalid_issuer(mock_jwks_client, mock_jwt):
    mock_jwt.decode.side_effect = InvalidIssuerError("Invalid issuer")
    mock_logger = MagicMock()

    with pytest.raises(InvalidTokenError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN,
            TEST_USER_POOL_ID,
            TEST_CLIENT_ID,
            TEST_AWS_REGION,
            mock_logger,
        )
    assert "Invalid issuer" in str(exc_info.value)


def test_expired_token(mock_jwks_client, mock_jwt):
    """
    Tests that get_sub_from_id_token raises InvalidTokenError when the token is expired.

    Simulates an expired JWT by configuring the mock to raise ExpiredSignatureError, and asserts that the resulting exception contains the expected error message.
    """
    mock_jwt.decode.side_effect = ExpiredSignatureError("Token has expired")
    mock_logger = MagicMock()

    with pytest.raises(InvalidTokenError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN,
            TEST_USER_POOL_ID,
            TEST_CLIENT_ID,
            TEST_AWS_REGION,
            mock_logger,
        )
    assert "Token has expired" in str(exc_info.value)


def test_jwt_processing_error(mock_jwks_client, mock_jwt):
    """
    Tests that get_sub_from_id_token raises InvalidTokenError when a generic JWT processing error occurs.

    Simulates a PyJWTError during token decoding and verifies that the resulting exception contains the expected error message.
    """
    mock_jwt.decode.side_effect = PyJWTError("JWT processing failed")
    mock_logger = MagicMock()

    with pytest.raises(InvalidTokenError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN,
            TEST_USER_POOL_ID,
            TEST_CLIENT_ID,
            TEST_AWS_REGION,
            mock_logger,
        )
    assert "JWT processing failed" in str(exc_info.value)


def test_auth_configuration_error(mock_jwks_client, mock_jwt):
    """
    Tests that an authentication configuration error is raised when the JWKS client fails to fetch signing keys.

    Simulates a failure in retrieving the JWKS signing key, asserting that `get_sub_from_id_token` raises `AuthConfigurationError` with an appropriate error message.
    """
    mock_jwks_client.return_value.get_signing_key_from_jwt.side_effect = PyJWTError(
        "Failed to fetch jwks.json"
    )
    mock_logger = MagicMock()

    with pytest.raises(AuthConfigurationError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN,
            TEST_USER_POOL_ID,
            TEST_CLIENT_ID,
            TEST_AWS_REGION,
            mock_logger,
        )
    assert "Auth configuration error" in str(exc_info.value)


def test_unexpected_error(mock_jwks_client, mock_jwt):
    """
    Tests that an unexpected exception during JWKS key retrieval raises AuthVerificationError.

    Verifies that if an unexpected error occurs while fetching the signing key, the get_sub_from_id_token function raises AuthVerificationError with the appropriate error message.
    """
    mock_jwks_client.return_value.get_signing_key_from_jwt.side_effect = Exception(
        "Unexpected error"
    )
    mock_logger = MagicMock()

    with pytest.raises(AuthVerificationError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN,
            TEST_USER_POOL_ID,
            TEST_CLIENT_ID,
            TEST_AWS_REGION,
            mock_logger,
        )
    assert "An unexpected authentication error occurred" in str(exc_info.value)


def test_no_user_pool_id(mock_jwks_client, mock_jwt):
    """
    Tests that get_sub_from_id_token raises AuthConfigurationError when the Cognito User Pool ID is missing.
    """
    mock_logger = MagicMock()

    with pytest.raises(AuthConfigurationError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN, None, TEST_CLIENT_ID, TEST_AWS_REGION, mock_logger
        )

    assert "Invalid or missing Cognito User Pool ID" in str(exc_info.value)


def test_no_client_id(mock_jwks_client, mock_jwt):
    """
    Tests that get_sub_from_id_token raises AuthConfigurationError when the Cognito Client ID is missing.
    """
    mock_logger = MagicMock()

    with pytest.raises(AuthConfigurationError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN, TEST_USER_POOL_ID, None, TEST_AWS_REGION, mock_logger
        )

    assert "Invalid or missing Cognito Client ID" in str(exc_info.value)
