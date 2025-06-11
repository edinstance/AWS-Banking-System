import json

import pytest
from jwt.exceptions import (
    PyJWTError,
    InvalidAudienceError,
    InvalidIssuerError,
    ExpiredSignatureError,
)

from functions.record_transactions.record_transactions.auth import (
    get_sub_from_id_token,
    authenticate_user,
)
from functions.record_transactions.record_transactions.exceptions import (
    MissingSubClaimError,
    InvalidTokenError,
    AuthConfigurationError,
    AuthVerificationError,
)
from tests.record_transaction_tests.conftest import (
    TEST_SUB,
    TEST_ID_TOKEN,
    TEST_USER_POOL_ID,
    TEST_CLIENT_ID,
    TEST_AWS_REGION,
)


def test_successful_token_verification(mock_jwks_client, mock_jwt):
    mock_jwt.decode.return_value = {"token_use": "id", "sub": TEST_SUB}

    result = get_sub_from_id_token(
        TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
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
    mock_jwt.decode.return_value = {"token_use": "id"}

    with pytest.raises(MissingSubClaimError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
        )
    assert "missing the 'sub' claim" in str(exc_info.value)


def test_invalid_token_use(mock_jwks_client, mock_jwt):
    mock_jwt.decode.return_value = {"token_use": "access", "sub": TEST_SUB}

    with pytest.raises(InvalidTokenError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
        )
    assert "Token is not an ID token" in str(exc_info.value)


def test_invalid_audience(mock_jwks_client, mock_jwt):
    mock_jwt.decode.side_effect = InvalidAudienceError("Invalid audience")

    with pytest.raises(InvalidTokenError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
        )
    assert "Invalid audience" in str(exc_info.value)


def test_invalid_issuer(mock_jwks_client, mock_jwt):
    mock_jwt.decode.side_effect = InvalidIssuerError("Invalid issuer")

    with pytest.raises(InvalidTokenError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
        )
    assert "Invalid issuer" in str(exc_info.value)


def test_expired_token(mock_jwks_client, mock_jwt):
    mock_jwt.decode.side_effect = ExpiredSignatureError("Token has expired")

    with pytest.raises(InvalidTokenError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
        )
    assert "Token has expired" in str(exc_info.value)


def test_jwt_processing_error(mock_jwks_client, mock_jwt):
    mock_jwt.decode.side_effect = PyJWTError("JWT processing failed")

    with pytest.raises(InvalidTokenError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
        )
    assert "JWT processing failed" in str(exc_info.value)


def test_auth_configuration_error(mock_jwks_client, mock_jwt):
    mock_jwks_client.return_value.get_signing_key_from_jwt.side_effect = PyJWTError(
        "Failed to fetch jwks.json"
    )

    with pytest.raises(AuthConfigurationError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
        )
    assert "Auth configuration error" in str(exc_info.value)


def test_unexpected_error(mock_jwks_client, mock_jwt):
    mock_jwks_client.return_value.get_signing_key_from_jwt.side_effect = Exception(
        "Unexpected error"
    )

    with pytest.raises(AuthVerificationError) as exc_info:
        get_sub_from_id_token(
            TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
        )
    assert "An unexpected authentication error occurred" in str(exc_info.value)


def test_no_user_pool_id(mock_jwks_client, mock_jwt):
    with pytest.raises(AuthConfigurationError) as exc_info:
        get_sub_from_id_token(TEST_ID_TOKEN, None, TEST_CLIENT_ID, TEST_AWS_REGION)

    assert "Invalid or missing Cognito User Pool ID" in str(exc_info.value)


def test_no_client_id(mock_jwks_client, mock_jwt):
    with pytest.raises(AuthConfigurationError) as exc_info:
        get_sub_from_id_token(TEST_ID_TOKEN, TEST_USER_POOL_ID, None, TEST_AWS_REGION)

    assert "Invalid or missing Cognito Client ID" in str(exc_info.value)


def test_authenticate_user_missing_authorization(valid_event, empty_headers):
    valid_event["headers"].pop("Authorization")

    user_id, response = authenticate_user(
        valid_event, empty_headers, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
    )

    response_body = json.loads(response["body"])

    assert user_id is None
    assert response["statusCode"] == 401
    assert (
        "Unauthorized: User identity could not be determined. Please ensure a valid token is provided."
        in response_body["error"]
    )


def test_authenticate_user_invalid_token(mock_auth, valid_event, headers_with_jwt):
    mock_auth.side_effect = InvalidTokenError("Signature verification failed")

    user_id, response = authenticate_user(
        valid_event,
        headers_with_jwt["headers"],
        TEST_USER_POOL_ID,
        TEST_CLIENT_ID,
        TEST_AWS_REGION,
    )

    response_body = json.loads(response["body"])

    assert user_id is None
    assert response["statusCode"] == 401
    assert (
        response_body["error"]
        == "Unauthorized: Invalid authentication token (Signature verification failed)"
    )


def test_authenticate_user_missing_sub_claim(mock_auth, valid_event, headers_with_jwt):
    mock_auth.side_effect = MissingSubClaimError("Missing sub claim")

    user_id, response = authenticate_user(
        valid_event,
        headers_with_jwt["headers"],
        TEST_USER_POOL_ID,
        TEST_CLIENT_ID,
        TEST_AWS_REGION,
    )

    response_body = json.loads(response["body"])

    assert user_id is None
    assert response["statusCode"] == 401
    assert (
        response_body["error"]
        == "Unauthorized: Invalid authentication token (Missing sub claim)"
    )


def test_authenticate_user_auth_configuration_error(
    mock_auth, valid_event, headers_with_jwt
):
    mock_auth.side_effect = AuthConfigurationError("Config error")

    user_id, response = authenticate_user(
        valid_event,
        headers_with_jwt["headers"],
        TEST_USER_POOL_ID,
        TEST_CLIENT_ID,
        TEST_AWS_REGION,
    )

    assert response["statusCode"] == 500
    assert "Server authentication configuration error" in response["body"]


def test_authenticate_user_verification_error(mock_auth, valid_event, headers_with_jwt):
    mock_auth.side_effect = AuthVerificationError("Verification error")

    user_id, response = authenticate_user(
        valid_event,
        headers_with_jwt["headers"],
        TEST_USER_POOL_ID,
        TEST_CLIENT_ID,
        TEST_AWS_REGION,
    )

    assert response["statusCode"] == 500
    assert "Internal authentication error" in response["body"]


def test_authenticate_user_unexpected_error(mock_auth, valid_event, headers_with_jwt):
    mock_auth.side_effect = Exception("Unknown error")

    user_id, response = authenticate_user(
        valid_event,
        headers_with_jwt["headers"],
        TEST_USER_POOL_ID,
        TEST_CLIENT_ID,
        TEST_AWS_REGION,
    )

    assert response["statusCode"] == 500
    assert "An unexpected error occurred during authentication." in response["body"]


def test_authenticate_user_no_user_id(mock_auth, valid_event, headers_with_jwt):
    mock_auth.return_value = None

    user_id, response = authenticate_user(
        valid_event,
        headers_with_jwt["headers"],
        TEST_USER_POOL_ID,
        TEST_CLIENT_ID,
        TEST_AWS_REGION,
    )

    assert user_id is None
    assert response["statusCode"] == 401
    assert (
        "Unauthorized: User identity could not be determined. Please ensure a valid token is provided."
        in response["body"]
    )
