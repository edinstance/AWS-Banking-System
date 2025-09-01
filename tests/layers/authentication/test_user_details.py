import uuid
from unittest.mock import patch

import pytest

from authentication.user_details import get_user_attributes
from tests.layers.authentication.conftest import TEST_AWS_REGION, TEST_USER_POOL_ID
from botocore.exceptions import ClientError


class TestUserDetails:

    def test_success(self, mock_cognito_client, mock_logger):
        username = "test_user"
        expected_attributes = {
            "sub": str(uuid.uuid4()),
            "email": "test@example.com",
            "name": "Test User",
            "email_verified": "true",
        }

        mock_response = {
            "UserAttributes": [
                {"Name": "sub", "Value": expected_attributes["sub"]},
                {"Name": "email", "Value": expected_attributes["email"]},
                {"Name": "name", "Value": expected_attributes["name"]},
                {
                    "Name": "email_verified",
                    "Value": expected_attributes["email_verified"],
                },
            ]
        }

        mock_cognito_client.admin_get_user.return_value = mock_response

        with patch("authentication.user_details.boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = mock_cognito_client

            result = get_user_attributes(
                aws_region=TEST_AWS_REGION,
                logger=mock_logger,
                username=username,
                user_pool_id=TEST_USER_POOL_ID,
            )

        assert result == expected_attributes
        mock_cognito_client.admin_get_user.assert_called_once_with(
            UserPoolId=TEST_USER_POOL_ID, Username=username
        )
        mock_logger.info.assert_called_once_with(
            f"Fetched attributes for user: {username}."
        )
        mock_boto3_client.assert_called_once_with(
            "cognito-idp", region_name=TEST_AWS_REGION
        )

    def test_cognito_exception(self, mock_cognito_client, mock_logger):
        username = "test_user"
        expected_exception = Exception("Cognito service error")

        mock_cognito_client.admin_get_user.side_effect = expected_exception

        with patch("authentication.user_details.boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = mock_cognito_client

            with pytest.raises(Exception) as exception_info:
                get_user_attributes(
                    aws_region=TEST_AWS_REGION,
                    logger=mock_logger,
                    username=username,
                    user_pool_id=TEST_USER_POOL_ID,
                )

        assert exception_info.value == expected_exception
        mock_logger.exception.assert_called_once_with(
            f"Failed to fetch user {username} from Cognito"
        )
        mock_cognito_client.admin_get_user.assert_called_once_with(
            UserPoolId=TEST_USER_POOL_ID, Username=username
        )

    def test_empty_user_attributes(self, mock_cognito_client, mock_logger):
        username = "test_user"
        mock_response = {"UserAttributes": []}

        mock_cognito_client.admin_get_user.return_value = mock_response

        with patch("authentication.user_details.boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = mock_cognito_client

            result = get_user_attributes(
                aws_region=TEST_AWS_REGION,
                logger=mock_logger,
                username=username,
                user_pool_id=TEST_USER_POOL_ID,
            )

        assert result == {}
        mock_logger.info.assert_called_once_with(
            f"Fetched attributes for user: {username}."
        )

    def test_specific_cognito_exceptions(self, mock_cognito_client, mock_logger):
        username = "test_user"

        error_response = {
            "Error": {"Code": "UserNotFoundException", "Message": "User does not exist"}
        }
        user_not_found_exception = ClientError(error_response, "AdminGetUser")

        mock_cognito_client.admin_get_user.side_effect = user_not_found_exception

        with patch("authentication.user_details.boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = mock_cognito_client

            with pytest.raises(ClientError) as exception_info:
                get_user_attributes(
                    aws_region=TEST_AWS_REGION,
                    logger=mock_logger,
                    username=username,
                    user_pool_id=TEST_USER_POOL_ID,
                )

        assert exception_info.value == user_not_found_exception
        mock_logger.exception.assert_called_once_with(
            f"Failed to fetch user {username} from Cognito"
        )
