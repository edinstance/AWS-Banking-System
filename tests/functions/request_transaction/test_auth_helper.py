# import json
#
# import pytest
# from jwt.exceptions import (
#     PyJWTError,
#     InvalidAudienceError,
#     InvalidIssuerError,
#     ExpiredSignatureError,
# )
#
# from functions.request_transaction.request_transaction.auth import (
#     get_sub_from_id_token,
#     authenticate_user,
# )
# from functions.request_transaction.request_transaction.exceptions import (
#     MissingSubClaimError,
#     InvalidTokenError,
#     AuthConfigurationError,
#     AuthVerificationError,
# )
# from tests.functions.request_transaction.conftest import (
#     TEST_SUB,
#     TEST_ID_TOKEN,
#     TEST_USER_POOL_ID,
#     TEST_CLIENT_ID,
#     TEST_AWS_REGION,
# )
#
#
# def test_successful_token_verification(mock_jwks_client, mock_jwt):
#     mock_jwt.decode.return_value = {"token_use": "id", "sub": TEST_SUB}
#
#     result = get_sub_from_id_token(
#         TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
#     )
#
#     assert result == TEST_SUB
#     mock_jwt.decode.assert_called_once_with(
#         TEST_ID_TOKEN,
#         "dummy_key",
#         algorithms=["RS256"],
#         audience=TEST_CLIENT_ID,
#         issuer=f"https://cognito-idp.{TEST_AWS_REGION}.amazonaws.com/{TEST_USER_POOL_ID}",
#     )
#
#
# def test_missing_sub_claim(mock_jwks_client, mock_jwt):
#     """
#     Tests that get_sub_from_id_token raises MissingSubClaimError when the ID token payload lacks the 'sub' claim.
#     """
#     mock_jwt.decode.return_value = {"token_use": "id"}
#
#     with pytest.raises(MissingSubClaimError) as exc_info:
#         get_sub_from_id_token(
#             TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
#         )
#     assert "missing the 'sub' claim" in str(exc_info.value)
#
#
# def test_invalid_token_use(mock_jwks_client, mock_jwt):
#     """
#     Tests that get_sub_from_id_token raises InvalidTokenError when the token's 'token_use' claim is not 'id'.
#     """
#     mock_jwt.decode.return_value = {"token_use": "access", "sub": TEST_SUB}
#
#     with pytest.raises(InvalidTokenError) as exc_info:
#         get_sub_from_id_token(
#             TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
#         )
#     assert "Token is not an ID token" in str(exc_info.value)
#
#
# def test_invalid_audience(mock_jwks_client, mock_jwt):
#     """
#     Tests that get_sub_from_id_token raises InvalidTokenError when the token audience is invalid.
#     """
#     mock_jwt.decode.side_effect = InvalidAudienceError("Invalid audience")
#
#     with pytest.raises(InvalidTokenError) as exc_info:
#         get_sub_from_id_token(
#             TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
#         )
#     assert "Invalid audience" in str(exc_info.value)
#
#
# def test_invalid_issuer(mock_jwks_client, mock_jwt):
#     mock_jwt.decode.side_effect = InvalidIssuerError("Invalid issuer")
#
#     with pytest.raises(InvalidTokenError) as exc_info:
#         get_sub_from_id_token(
#             TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
#         )
#     assert "Invalid issuer" in str(exc_info.value)
#
#
# def test_expired_token(mock_jwks_client, mock_jwt):
#     """
#     Tests that get_sub_from_id_token raises InvalidTokenError when the token is expired.
#
#     Simulates an expired JWT by configuring the mock to raise ExpiredSignatureError, and asserts that the resulting exception contains the expected error message.
#     """
#     mock_jwt.decode.side_effect = ExpiredSignatureError("Token has expired")
#
#     with pytest.raises(InvalidTokenError) as exc_info:
#         get_sub_from_id_token(
#             TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
#         )
#     assert "Token has expired" in str(exc_info.value)
#
#
# def test_jwt_processing_error(mock_jwks_client, mock_jwt):
#     """
#     Tests that get_sub_from_id_token raises InvalidTokenError when a generic JWT processing error occurs.
#
#     Simulates a PyJWTError during token decoding and verifies that the resulting exception contains the expected error message.
#     """
#     mock_jwt.decode.side_effect = PyJWTError("JWT processing failed")
#
#     with pytest.raises(InvalidTokenError) as exc_info:
#         get_sub_from_id_token(
#             TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
#         )
#     assert "JWT processing failed" in str(exc_info.value)
#
#
# def test_auth_configuration_error(mock_jwks_client, mock_jwt):
#     """
#     Tests that an authentication configuration error is raised when the JWKS client fails to fetch signing keys.
#
#     Simulates a failure in retrieving the JWKS signing key, asserting that `get_sub_from_id_token` raises `AuthConfigurationError` with an appropriate error message.
#     """
#     mock_jwks_client.return_value.get_signing_key_from_jwt.side_effect = PyJWTError(
#         "Failed to fetch jwks.json"
#     )
#
#     with pytest.raises(AuthConfigurationError) as exc_info:
#         get_sub_from_id_token(
#             TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
#         )
#     assert "Auth configuration error" in str(exc_info.value)
#
#
# def test_unexpected_error(mock_jwks_client, mock_jwt):
#     """
#     Tests that an unexpected exception during JWKS key retrieval raises AuthVerificationError.
#
#     Verifies that if an unexpected error occurs while fetching the signing key, the get_sub_from_id_token function raises AuthVerificationError with the appropriate error message.
#     """
#     mock_jwks_client.return_value.get_signing_key_from_jwt.side_effect = Exception(
#         "Unexpected error"
#     )
#
#     with pytest.raises(AuthVerificationError) as exc_info:
#         get_sub_from_id_token(
#             TEST_ID_TOKEN, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
#         )
#     assert "An unexpected authentication error occurred" in str(exc_info.value)
#
#
# def test_no_user_pool_id(mock_jwks_client, mock_jwt):
#     """
#     Tests that get_sub_from_id_token raises AuthConfigurationError when the Cognito User Pool ID is missing.
#     """
#     with pytest.raises(AuthConfigurationError) as exc_info:
#         get_sub_from_id_token(TEST_ID_TOKEN, None, TEST_CLIENT_ID, TEST_AWS_REGION)
#
#     assert "Invalid or missing Cognito User Pool ID" in str(exc_info.value)
#
#
# def test_no_client_id(mock_jwks_client, mock_jwt):
#     """
#     Tests that get_sub_from_id_token raises AuthConfigurationError when the Cognito Client ID is missing.
#     """
#     with pytest.raises(AuthConfigurationError) as exc_info:
#         get_sub_from_id_token(TEST_ID_TOKEN, TEST_USER_POOL_ID, None, TEST_AWS_REGION)
#
#     assert "Invalid or missing Cognito Client ID" in str(exc_info.value)
#
#
# def test_authenticate_user_missing_authorization(valid_event, empty_headers):
#     """
#     Tests that authenticate_user returns a 401 response when the Authorization header is missing.
#
#     Removes the "Authorization" header from the event and verifies that the function returns None for the user ID and a 401 response with an appropriate error message.
#     """
#     valid_event["headers"].pop("Authorization")
#
#     user_id, response = authenticate_user(
#         valid_event, empty_headers, TEST_USER_POOL_ID, TEST_CLIENT_ID, TEST_AWS_REGION
#     )
#
#     response_body = json.loads(response["body"])
#
#     assert user_id is None
#     assert response["statusCode"] == 401
#     assert (
#         "Unauthorized: User identity could not be determined. Please ensure a valid token is provided."
#         in response_body["error"]
#     )
#
#
# def test_authenticate_user_invalid_token(mock_auth, valid_event, headers_with_jwt):
#     """
#     Tests that authenticate_user returns a 401 response with an appropriate error message when an invalid authentication token is provided.
#     """
#     mock_auth.side_effect = InvalidTokenError("Signature verification failed")
#
#     user_id, response = authenticate_user(
#         valid_event,
#         headers_with_jwt["headers"],
#         TEST_USER_POOL_ID,
#         TEST_CLIENT_ID,
#         TEST_AWS_REGION,
#     )
#
#     response_body = json.loads(response["body"])
#
#     assert user_id is None
#     assert response["statusCode"] == 401
#     assert (
#         response_body["error"]
#         == "Unauthorized: Invalid authentication token (Signature verification failed)"
#     )
#
#
# def test_authenticate_user_missing_sub_claim(mock_auth, valid_event, headers_with_jwt):
#     """
#     Tests that authenticate_user returns a 401 response with an appropriate error message when the ID token is missing the 'sub' claim.
#     """
#     mock_auth.side_effect = MissingSubClaimError("Missing sub claim")
#
#     user_id, response = authenticate_user(
#         valid_event,
#         headers_with_jwt["headers"],
#         TEST_USER_POOL_ID,
#         TEST_CLIENT_ID,
#         TEST_AWS_REGION,
#     )
#
#     response_body = json.loads(response["body"])
#
#     assert user_id is None
#     assert response["statusCode"] == 401
#     assert (
#         response_body["error"]
#         == "Unauthorized: Invalid authentication token (Missing sub claim)"
#     )
#
#
# def test_authenticate_user_auth_configuration_error(
#     mock_auth, valid_event, headers_with_jwt
# ):
#     """
#     Tests that authenticate_user returns a 500 response with an appropriate error message when an AuthConfigurationError is raised during authentication.
#     """
#     mock_auth.side_effect = AuthConfigurationError("Config error")
#
#     user_id, response = authenticate_user(
#         valid_event,
#         headers_with_jwt["headers"],
#         TEST_USER_POOL_ID,
#         TEST_CLIENT_ID,
#         TEST_AWS_REGION,
#     )
#
#     assert response["statusCode"] == 500
#     assert "Server authentication configuration error" in response["body"]
#
#
# def test_authenticate_user_verification_error(mock_auth, valid_event, headers_with_jwt):
#     """
#     Tests that authenticate_user returns a 500 response with an internal authentication error message when AuthVerificationError is raised during token verification.
#     """
#     mock_auth.side_effect = AuthVerificationError("Verification error")
#
#     user_id, response = authenticate_user(
#         valid_event,
#         headers_with_jwt["headers"],
#         TEST_USER_POOL_ID,
#         TEST_CLIENT_ID,
#         TEST_AWS_REGION,
#     )
#
#     assert response["statusCode"] == 500
#     assert "Internal authentication error" in response["body"]
#
#
# def test_authenticate_user_unexpected_error(mock_auth, valid_event, headers_with_jwt):
#     """
#     Tests that authenticate_user returns a 500 response with an appropriate error message when an unexpected exception is raised during authentication.
#     """
#     mock_auth.side_effect = Exception("Unknown error")
#
#     user_id, response = authenticate_user(
#         valid_event,
#         headers_with_jwt["headers"],
#         TEST_USER_POOL_ID,
#         TEST_CLIENT_ID,
#         TEST_AWS_REGION,
#     )
#
#     assert response["statusCode"] == 500
#     assert "An unexpected error occurred during authentication." in response["body"]
#
#
# def test_authenticate_user_no_user_id(mock_auth, valid_event, headers_with_jwt):
#     """
#     Tests that `authenticate_user` returns a 401 response when no user ID is extracted from a valid token.
#
#     Verifies that if the authentication helper returns `None` for the user ID, the function responds with an appropriate error message and status code.
#     """
#     mock_auth.return_value = None
#
#     user_id, response = authenticate_user(
#         valid_event,
#         headers_with_jwt["headers"],
#         TEST_USER_POOL_ID,
#         TEST_CLIENT_ID,
#         TEST_AWS_REGION,
#     )
#
#     assert user_id is None
#     assert response["statusCode"] == 401
#     assert (
#         "Unauthorized: User identity could not be determined. Please ensure a valid token is provided."
#         in response["body"]
#     )
