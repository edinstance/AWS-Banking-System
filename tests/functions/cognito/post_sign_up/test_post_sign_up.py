import uuid
from unittest.mock import patch, MagicMock

import pytest
from botocore.exceptions import ClientError

from functions.cognito.post_sign_up.post_sign_up.app import lambda_handler

TEST_USER_ID = uuid.uuid4()
TEST_EMAIL = "test@example.com"

event = {
    "userName": TEST_USER_ID,
    "request": {
        "userAttributes": {
            "sub": TEST_USER_ID,
            "email_verified": "false",
            "cognito:user_status": "CONFIRMED",
            "email": TEST_EMAIL,
        }
    },
}


class TestPostSignUp:
    def test_table_initialization_with_environment_variable(
        self, app_with_mocked_accounts_table
    ):
        """Test table initialization when ACCOUNTS_TABLE_NAME is set."""
        assert app_with_mocked_accounts_table.table is not None
        assert (
            app_with_mocked_accounts_table.ACCOUNTS_TABLE_NAME == "test-accounts-table"
        )

    def test_no_table_initialised(self, mock_context):
        """
        Test that the lambda_handler returns the original event unchanged when the DynamoDB table is not initialised.
        """
        with patch("functions.cognito.post_sign_up.post_sign_up.app.table", None):
            response = lambda_handler(event, mock_context)
            assert response == event

    def test_successful_account_creation(self, mock_context):
        """
        Test that the lambda_handler returns the original event after successful account creation when SES is disabled.
        """
        mock_table = MagicMock()
        mock_account_id = str(uuid.uuid4())

        with patch(
            "functions.cognito.post_sign_up.post_sign_up.app.table", mock_table
        ), patch(
            "functions.cognito.post_sign_up.post_sign_up.app.create_account_if_not_exists",
            return_value=mock_account_id,
        ), patch(
            "functions.cognito.post_sign_up.post_sign_up.app.SES_ENABLED", False
        ):
            response = lambda_handler(event, mock_context)

            assert response == event

    def test_successful_email_sending(self, aws_ses_credentials, mock_context):
        """
        Test that the lambda_handler returns the original event when account creation and email sending succeed with SES enabled.
        """
        mock_table = MagicMock()
        mock_account_id = str(uuid.uuid4())

        with patch(
            "functions.cognito.post_sign_up.post_sign_up.app.table", mock_table
        ), patch(
            "functions.cognito.post_sign_up.post_sign_up.app.create_account_if_not_exists",
            return_value=mock_account_id,
        ), patch(
            "functions.cognito.post_sign_up.post_sign_up.app.SES_ENABLED", True
        ), patch(
            "functions.cognito.post_sign_up.post_sign_up.app.send_user_email",
            return_value=True,
        ):
            response = lambda_handler(event, mock_context)

            assert response == event

    def test_failed_email_sending(self, aws_ses_credentials, mock_context):
        """
        Test that the lambda_handler raises an exception when email sending fails after account creation with SES enabled.

        Simulates successful account creation but failed email delivery, and asserts that an exception containing "Failed to send email" is raised.
        """
        mock_table = MagicMock()
        mock_account_id = str(uuid.uuid4())

        with patch(
            "functions.cognito.post_sign_up.post_sign_up.app.table", mock_table
        ), patch(
            "functions.cognito.post_sign_up.post_sign_up.app.create_account_if_not_exists",
            return_value=mock_account_id,
        ), patch(
            "functions.cognito.post_sign_up.post_sign_up.app.SES_ENABLED", True
        ), patch(
            "functions.cognito.post_sign_up.post_sign_up.app.send_user_email",
            return_value=False,
        ):
            with pytest.raises(Exception) as exception_info:
                lambda_handler(event, mock_context)

            assert "Failed to send email" in str(exception_info.value)

    def test_exception_during_account_creation(self, mock_context):
        """
        Test that the lambda_handler raises a ClientError when account creation fails due to a DynamoDB error.
        """
        mock_table = MagicMock()
        error_message = "DynamoDB error"

        with patch(
            "functions.cognito.post_sign_up.post_sign_up.app.table", mock_table
        ), patch(
            "functions.cognito.post_sign_up.post_sign_up.app.create_account_if_not_exists",
            side_effect=ClientError({"Error": {"Message": error_message}}, "PutItem"),
        ):
            with pytest.raises(ClientError):
                lambda_handler(event, mock_context)

    def test_no_account_id_returned(self, mock_context):
        """
        Test that the lambda_handler raises an exception when account creation does not return an account ID.

        Asserts that an appropriate error message is included in the raised exception.
        """
        mock_table = MagicMock()

        with patch(
            "functions.cognito.post_sign_up.post_sign_up.app.table", mock_table
        ), patch(
            "functions.cognito.post_sign_up.post_sign_up.app.create_account_if_not_exists",
            return_value=None,
        ):
            with pytest.raises(Exception) as exception_info:
                lambda_handler(event, mock_context)

            assert "Failed to create account for user" in str(exception_info.value)

    def test_missing_username(self, mock_context):
        """
        Test that the lambda_handler raises a ValueError when the event is missing the userName key.

        Asserts that the exception message contains 'user_id is required'.
        """
        mock_table = MagicMock()
        event_without_username = {
            "request": {
                "userAttributes": {
                    "sub": TEST_USER_ID,
                    "email_verified": "false",
                    "cognito:user_status": "CONFIRMED",
                    "email": TEST_EMAIL,
                }
            }
        }

        with patch("functions.cognito.post_sign_up.post_sign_up.app.table", mock_table):
            with pytest.raises(ValueError) as exception_info:
                lambda_handler(event_without_username, mock_context)

            assert "user_id is required" in str(exception_info.value)

    def test_missing_email_with_ses_enabled(self, mock_context):
        """
        Test that the lambda_handler raises an exception when SES is enabled but the user's email is missing and email sending fails.

        Simulates a post sign-up event without an email attribute, mocks successful account creation, enables SES, and forces email sending to fail. Asserts that an exception with a relevant error message is raised.
        """
        mock_table = MagicMock()
        mock_account_id = str(uuid.uuid4())
        event_without_email = {
            "userName": TEST_USER_ID,
            "request": {
                "userAttributes": {
                    "sub": TEST_USER_ID,
                    "email_verified": "false",
                    "cognito:user_status": "CONFIRMED",
                    # email is missing
                }
            },
        }

        with patch(
            "functions.cognito.post_sign_up.post_sign_up.app.table", mock_table
        ), patch(
            "functions.cognito.post_sign_up.post_sign_up.app.create_account_if_not_exists",
            return_value=mock_account_id,
        ), patch(
            "functions.cognito.post_sign_up.post_sign_up.app.SES_ENABLED", True
        ), patch(
            "functions.cognito.post_sign_up.post_sign_up.app.send_user_email",
            return_value=False,
        ):
            with pytest.raises(Exception) as exception_info:
                lambda_handler(event_without_email, mock_context)

            # The lambda_handler raises an exception when email sending fails
            assert "Failed to send email" in str(exception_info.value)
