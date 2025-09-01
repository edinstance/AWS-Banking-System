import pytest
from unittest.mock import patch
from botocore.exceptions import ClientError


class TestNotifyClientLambdaHandler:
    """Test cases for the notify_client Lambda handler."""

    def test_successful_notification_with_attachment(
        self,
        notify_client_app_with_mocks,
        sample_event,
        mock_context,
        mock_user_attributes,
        mock_pdf_bytes,
    ):
        """Test successful notification with PDF attachment."""
        app = notify_client_app_with_mocks

        with patch(
            "functions.monthly_reports.accounts.notify_client.notify_client.app.get_user_attributes"
        ) as mock_get_user:
            mock_get_user.return_value = mock_user_attributes

            with patch(
                "functions.monthly_reports.accounts.notify_client.notify_client.app.send_user_email_with_attachment"
            ) as mock_send_email:
                mock_send_email.return_value = {"MessageId": "test-message-id-123"}

                result = app.lambda_handler(sample_event, mock_context)

                mock_get_user.assert_called_once_with(
                    aws_region="eu-west-2",
                    logger=app.logger,
                    username=sample_event["userId"],
                    user_pool_id="eu-west-2_testpool123",
                )

                app.s3.head_object.assert_called_once_with(
                    Bucket="test-reports-bucket",
                    Key=f"{sample_event['accountId']}/{sample_event['statementPeriod']}.pdf",
                )

                mock_send_email.assert_called_once_with(
                    aws_region="eu-west-2",
                    logger=app.logger,
                    sender_email="noreply@testbank.com",
                    to_addresses=[mock_user_attributes["email"]],
                    subject_data=f"Your Account Statement for {sample_event['statementPeriod']}",
                    body_text=f"Hello {mock_user_attributes['name']},\n\nPlease find your account statement attached.\n\nKind Regards.",
                    attachment_bytes=mock_pdf_bytes,
                    attachment_filename="statement.pdf",
                )

                expected_response = {
                    "status": "success",
                    "messageId": "test-message-id-123",
                    "mode": "attachment",
                }
                assert result == expected_response

    def test_successful_notification_with_link(
        self,
        notify_client_app_with_mocks,
        sample_event,
        mock_context,
        mock_user_attributes,
        mock_presigned_url,
    ):
        app = notify_client_app_with_mocks

        app.s3.head_object.return_value = {"ContentLength": 8 * 1024 * 1024}  # 8MB

        with patch(
            "functions.monthly_reports.accounts.notify_client.notify_client.app.get_user_attributes"
        ) as mock_get_user:
            mock_get_user.return_value = mock_user_attributes

            with patch(
                "functions.monthly_reports.accounts.notify_client.notify_client.app.send_user_email"
            ) as mock_send_email:
                mock_send_email.return_value = {"MessageId": "test-message-id-456"}

                result = app.lambda_handler(sample_event, mock_context)

                mock_get_user.assert_called_once_with(
                    aws_region="eu-west-2",
                    logger=app.logger,
                    username=sample_event["userId"],
                    user_pool_id="eu-west-2_testpool123",
                )

                app.s3.head_object.assert_called_once_with(
                    Bucket="test-reports-bucket",
                    Key=f"{sample_event['accountId']}/{sample_event['statementPeriod']}.pdf",
                )

                app.s3.generate_presigned_url.assert_called_once_with(
                    "get_object",
                    Params={
                        "Bucket": "test-reports-bucket",
                        "Key": f"{sample_event['accountId']}/{sample_event['statementPeriod']}.pdf",
                    },
                    ExpiresIn=3600,
                )

                mock_send_email.assert_called_once_with(
                    aws_region="eu-west-2",
                    logger=app.logger,
                    sender_email="noreply@testbank.com",
                    to_addresses=[mock_user_attributes["email"]],
                    subject_data=f"Your Account Statement for {sample_event['statementPeriod']}",
                    text_body_data=(
                        f"Hello {mock_user_attributes['name']},\n\n"
                        f"Your account statement is ready.\n\n"
                        f"Download it here (valid for 1 hour):\n{mock_presigned_url}\n\n"
                        f"If you need a new link please request one through the API.\n\n"
                        f"Kind Regards."
                    ),
                )

                expected_response = {
                    "status": "success",
                    "messageId": "test-message-id-456",
                    "mode": "link",
                }
                assert result == expected_response

    def test_user_without_email_attribute(
        self, notify_client_app_with_mocks, sample_event, mock_context
    ):
        app = notify_client_app_with_mocks

        with patch(
            "functions.monthly_reports.accounts.notify_client.notify_client.app.get_user_attributes"
        ) as mock_get_user:
            mock_get_user.return_value = {"name": "John Doe"}

            with pytest.raises(
                ValueError,
                match=f"User {sample_event['userId']} has no email attribute in Cognito",
            ):
                app.lambda_handler(sample_event, mock_context)

            app.s3.head_object.assert_not_called()
            app.s3.get_object.assert_not_called()

    def test_s3_client_error(
        self,
        notify_client_app_with_mocks,
        sample_event,
        mock_context,
        mock_user_attributes,
    ):
        app = notify_client_app_with_mocks

        app.s3.head_object.side_effect = ClientError(
            error_response={
                "Error": {
                    "Code": "NoSuchKey",
                    "Message": "The specified key does not exist.",
                }
            },
            operation_name="HeadObject",
        )

        with patch(
            "functions.monthly_reports.accounts.notify_client.notify_client.app.get_user_attributes"
        ) as mock_get_user:
            mock_get_user.return_value = mock_user_attributes

            with pytest.raises(ClientError):
                app.lambda_handler(sample_event, mock_context)

    def test_email_sending_failure(
        self,
        notify_client_app_with_mocks,
        sample_event,
        mock_context,
        mock_user_attributes,
    ):
        app = notify_client_app_with_mocks

        with patch(
            "functions.monthly_reports.accounts.notify_client.notify_client.app.get_user_attributes"
        ) as mock_get_user:
            mock_get_user.return_value = mock_user_attributes

            with patch(
                "functions.monthly_reports.accounts.notify_client.notify_client.app.send_user_email_with_attachment"
            ) as mock_send_email:
                mock_send_email.return_value = None

                result = app.lambda_handler(sample_event, mock_context)

                expected_response = {
                    "status": "failed",
                    "messageId": None,
                    "mode": "attachment",
                }
                assert result == expected_response

    def test_email_sending_exception(
        self,
        notify_client_app_with_mocks,
        sample_event,
        mock_context,
        mock_user_attributes,
    ):
        app = notify_client_app_with_mocks

        with patch(
            "functions.monthly_reports.accounts.notify_client.notify_client.app.get_user_attributes"
        ) as mock_get_user:
            mock_get_user.return_value = mock_user_attributes

            with patch(
                "functions.monthly_reports.accounts.notify_client.notify_client.app.send_user_email_with_attachment"
            ) as mock_send_email:
                mock_send_email.side_effect = Exception("SES service unavailable")

                with pytest.raises(Exception, match="SES service unavailable"):
                    app.lambda_handler(sample_event, mock_context)

    def test_user_attributes_retrieval_failure(
        self, notify_client_app_with_mocks, sample_event, mock_context
    ):
        app = notify_client_app_with_mocks

        with patch(
            "functions.monthly_reports.accounts.notify_client.notify_client.app.get_user_attributes"
        ) as mock_get_user:
            mock_get_user.side_effect = Exception("Cognito service unavailable")

            with pytest.raises(Exception, match="Cognito service unavailable"):
                app.lambda_handler(sample_event, mock_context)

    def test_user_without_name_attribute(
        self, notify_client_app_with_mocks, sample_event, mock_context, mock_pdf_bytes
    ):
        app = notify_client_app_with_mocks

        with patch(
            "functions.monthly_reports.accounts.notify_client.notify_client.app.get_user_attributes"
        ) as mock_get_user:
            mock_get_user.return_value = {"email": "test@example.com"}

            with patch(
                "functions.monthly_reports.accounts.notify_client.notify_client.app.send_user_email_with_attachment"
            ) as mock_send_email:
                mock_send_email.return_value = {"MessageId": "test-message-id-123"}

                result = app.lambda_handler(sample_event, mock_context)

                mock_send_email.assert_called_once_with(
                    aws_region="eu-west-2",
                    logger=app.logger,
                    sender_email="noreply@testbank.com",
                    to_addresses=["test@example.com"],
                    subject_data=f"Your Account Statement for {sample_event['statementPeriod']}",
                    body_text="Hello Customer,\n\nPlease find your account statement attached.\n\nKind Regards.",
                    attachment_bytes=mock_pdf_bytes,
                    attachment_filename="statement.pdf",
                )

                expected_response = {
                    "status": "success",
                    "messageId": "test-message-id-123",
                    "mode": "attachment",
                }
                assert result == expected_response

    def test_exact_file_size_threshold(
        self,
        notify_client_app_with_mocks,
        sample_event,
        mock_context,
        mock_user_attributes,
    ):
        app = notify_client_app_with_mocks

        app.s3.head_object.return_value = {
            "ContentLength": 7 * 1024 * 1024
        }  # Exactly 7MB

        with patch(
            "functions.monthly_reports.accounts.notify_client.notify_client.app.get_user_attributes"
        ) as mock_get_user:
            mock_get_user.return_value = mock_user_attributes

            with patch(
                "functions.monthly_reports.accounts.notify_client.notify_client.app.send_user_email_with_attachment"
            ) as mock_send_email:
                mock_send_email.return_value = {"MessageId": "test-message-id-123"}

                result = app.lambda_handler(sample_event, mock_context)

                mock_send_email.assert_called_once()
                assert result["mode"] == "attachment"
