import json
from unittest.mock import patch, MagicMock

import pytest

from ses import get_ses_client, send_user_email, send_user_email_with_attachment


class TestGetSesClient:

    def test_get_ses_client_success(self):
        """
        Test that `get_ses_client` successfully creates and returns an SES client for the specified region and logs the initialisation message.
        """
        mock_logger = MagicMock()
        region = "eu-west-2"

        with patch("boto3.client") as mock_boto3_client:
            mock_client = MagicMock()
            mock_boto3_client.return_value = mock_client

            result = get_ses_client(region, mock_logger)

            mock_boto3_client.assert_called_once_with("ses", region_name=region)
            assert result == mock_client
            mock_logger.info.assert_called_once_with(
                "Initialized SES client with default endpoint"
            )

    def test_get_ses_client_exception(self):
        """
        Test that get_ses_client raises an exception and logs an error when SES client creation fails.
        """
        mock_logger = MagicMock()
        region = "eu-west-2"

        with patch("boto3.client") as mock_boto3_client:
            mock_boto3_client.side_effect = Exception("Connection error")

            with pytest.raises(Exception) as exc_info:
                get_ses_client(region, mock_logger)

            assert "Connection error" in str(exc_info.value)
            mock_logger.error.assert_called_once_with(
                "Failed to initialize SES client", exc_info=True
            )


class TestSendEmail:

    @pytest.fixture(autouse=True)
    def setup(self, mock_get_ses_client):
        """
        Initialises common test data and mock objects for SES email sending tests.

        This setup method prepares mock logger, email parameters, and mock SES client instances for use in test cases.
        """
        self.mock_logger = MagicMock()
        self.aws_region = "eu-west-2"
        self.sender_email = "sender@example.com"
        self.to_addresses = ["recipient@example.com"]
        self.subject_data = "Test Subject"
        self.subject_charset = "UTF-8"
        self.text_body_data = "This is the text body."
        self.html_body_data = "<html><body>This is the HTML body.</body></html>"
        self.reply_to_addresses = ["reply@example.com"]
        self.return_path = "bounce@example.com"
        self.tags = [{"Name": "Environment", "Value": "test"}]
        self.cc_addresses = ["cc@example.com"]
        self.bcc_addresses = ["bcc@example.com"]

        self.mock_get_client, self.mock_ses_client = mock_get_ses_client

    def test_send_user_email_success(self, mock_ses_client):
        """
        Test that send_user_email sends an email with all parameters and logs success.

        Verifies that the SES client's send_email method is called with the correct arguments, the logger records a success message, and the function returns True.
        """
        # Prepare a mock SES response
        mock_response = {"MessageId": "test-message-id-123"}
        self.mock_ses_client.send_email.return_value = mock_response

        result = send_user_email(
            aws_region=self.aws_region,
            logger=self.mock_logger,
            sender_email=self.sender_email,
            to_addresses=self.to_addresses,
            cc_addresses=self.cc_addresses,
            bcc_addresses=self.bcc_addresses,
            subject_data=self.subject_data,
            subject_charset=self.subject_charset,
            text_body_data=self.text_body_data,
            html_body_data=self.html_body_data,
            reply_to_addresses=self.reply_to_addresses,
            return_path=self.return_path,
            tags=self.tags,
        )

        self.mock_ses_client.send_email.assert_called_once_with(
            Source=self.sender_email,
            Destination={
                "ToAddresses": self.to_addresses,
                "CcAddresses": self.cc_addresses,
                "BccAddresses": self.bcc_addresses,
            },
            Message={
                "Subject": {"Data": self.subject_data, "Charset": self.subject_charset},
                "Body": {
                    "Text": {"Data": self.text_body_data, "Charset": "UTF-8"},
                    "Html": {"Data": self.html_body_data, "Charset": "UTF-8"},
                },
            },
            ReplyToAddresses=self.reply_to_addresses,
            ReturnPath=self.return_path,
            Tags=self.tags,
        )

        self.mock_logger.info.assert_called_once_with(
            f"Successfully sent email to {json.dumps(self.to_addresses)}, MessageId={mock_response['MessageId']}"
        )
        assert result == mock_response

    def test_send_user_email_exception(self, mock_ses_client):
        mock_exception = Exception("Simulated SES send error")
        self.mock_ses_client.send_email.side_effect = mock_exception

        with pytest.raises(Exception) as exc_info:
            send_user_email(
                aws_region=self.aws_region,
                logger=self.mock_logger,
                sender_email=self.sender_email,
                to_addresses=self.to_addresses,
                subject_data=self.subject_data,
                subject_charset=self.subject_charset,
                text_body_data=self.text_body_data,
            )

        assert "Simulated SES send error" in str(exc_info.value)
        self.mock_ses_client.send_email.assert_called_once()

        self.mock_logger.error.assert_called_once_with(
            f"Failed to send email: {mock_exception}", exc_info=True
        )

    def test_send_user_email_no_body(self, mock_ses_client):
        """
        Test that send_user_email returns False and logs an error when neither text nor HTML body is provided.
        """
        with pytest.raises(Exception) as exc_info:
            send_user_email(
                aws_region=self.aws_region,
                logger=self.mock_logger,
                sender_email=self.sender_email,
                to_addresses=self.to_addresses,
                subject_data=self.subject_data,
                subject_charset=self.subject_charset,
            )

        self.mock_ses_client.send_email.assert_not_called()
        self.mock_logger.error.assert_called_once_with(
            "Email must contain at least a text or HTML body."
        )

        assert str(exc_info.value) == "Email must contain at least a text or HTML body."


class TestSendEmailWithAttachment:
    @pytest.fixture(autouse=True)
    def setup(self, mock_get_ses_client):
        self.mock_logger = MagicMock()
        self.aws_region = "eu-west-2"
        self.sender_email = "sender@example.com"
        self.to_addresses = ["recipient@example.com"]
        self.cc_addresses = ["cc@example.com"]
        self.bcc_addresses = ["bcc@example.com"]
        self.subject_data = "Monthly Report"
        self.body_text = "Please find the report attached."
        self.attachment_bytes = b"dummy-bytes"
        self.attachment_filename = "report.pdf"
        self.mock_get_client, self.mock_ses_client = mock_get_ses_client

    def test_send_user_email_with_attachment_success(self):
        mock_response = {"MessageId": "raw-123"}
        self.mock_ses_client.send_raw_email.return_value = mock_response

        result = send_user_email_with_attachment(
            aws_region=self.aws_region,
            logger=self.mock_logger,
            sender_email=self.sender_email,
            to_addresses=self.to_addresses,
            subject_data=self.subject_data,
            body_text=self.body_text,
            attachment_bytes=self.attachment_bytes,
            attachment_filename=self.attachment_filename,
            cc_addresses=self.cc_addresses,
            bcc_addresses=self.bcc_addresses,
        )

        assert self.mock_ses_client.send_raw_email.call_count == 1
        kwargs = self.mock_ses_client.send_raw_email.call_args.kwargs

        assert kwargs["Source"] == self.sender_email
        assert set(kwargs["Destinations"]) == set(
            self.to_addresses + self.cc_addresses + self.bcc_addresses
        )

        assert isinstance(kwargs["RawMessage"]["Data"], str)
        raw_data = kwargs["RawMessage"]["Data"]
        assert self.subject_data in raw_data
        assert self.body_text in raw_data
        assert f'filename="{self.attachment_filename}"' in raw_data

        assert self.subject_data in raw_data
        assert self.body_text in raw_data
        assert f'filename="{self.attachment_filename}"' in raw_data

        self.mock_logger.info.assert_called_once_with(
            f"Successfully sent email with attachment to {json.dumps(self.to_addresses)}, "
            f"MessageId={mock_response['MessageId']}"
        )
        assert result == mock_response

    def test_send_user_email_with_attachment_exception(self):
        err = Exception("attachment send fail")
        self.mock_ses_client.send_raw_email.side_effect = err

        with pytest.raises(Exception) as exc:
            send_user_email_with_attachment(
                aws_region=self.aws_region,
                logger=self.mock_logger,
                sender_email=self.sender_email,
                to_addresses=self.to_addresses,
                subject_data=self.subject_data,
                body_text=self.body_text,
                attachment_bytes=self.attachment_bytes,
                attachment_filename=self.attachment_filename,
            )

        assert "attachment send fail" in str(exc.value)
        self.mock_logger.error.assert_called_once_with(
            f"Failed to send email with attachment: {err}", exc_info=True
        )
