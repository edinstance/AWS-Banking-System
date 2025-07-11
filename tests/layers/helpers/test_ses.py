import json
from unittest.mock import patch, MagicMock

import pytest

from ses import get_ses_client, send_user_email


class TestGetSesClient:

    def test_get_ses_client_success(self):
        mock_logger = MagicMock()
        region = "eu-west-2"

        with patch("boto3.client") as mock_boto3_resource:
            mock_resource = MagicMock()
            mock_boto3_resource.return_value = mock_resource

            result = get_ses_client(region, mock_logger)

            mock_boto3_resource.assert_called_once_with("ses", region_name=region)
            assert result == mock_resource
            mock_logger.info.assert_called_once_with(
                "Initialized SES client with default endpoint"
            )

    def test_get_ses_client_exception(self):
        mock_logger = MagicMock()
        region = "eu-west-2"

        with patch("boto3.client") as mock_boto3_resource:
            mock_boto3_resource.side_effect = Exception("Connection error")

            with pytest.raises(Exception) as exc_info:
                get_ses_client(region, mock_logger)

            assert "Connection error" in str(exc_info.value)
            mock_logger.error.assert_called_once_with(
                "Failed to initialize SES client", exc_info=True
            )


class TestSendEmail:

    @pytest.fixture(autouse=True)
    def setup(self, mock_get_ses_client):
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
            f"Successfully sent email to users: {json.dumps(self.to_addresses)}"
        )
        assert result is True

    def test_send_user_email_exception(self, mock_ses_client):
        mock_exception = Exception("Simulated SES send error")
        self.mock_ses_client.send_email.side_effect = mock_exception

        result = send_user_email(
            aws_region=self.aws_region,
            logger=self.mock_logger,
            sender_email=self.sender_email,
            to_addresses=self.to_addresses,
            subject_data=self.subject_data,
            subject_charset=self.subject_charset,
            text_body_data=self.text_body_data,
        )

        self.mock_ses_client.send_email.assert_called_once()

        self.mock_logger.error.assert_called_once_with(
            f"Failed to send email: {mock_exception}"
        )
        assert result is False

    def test_send_user_email_no_body(self, mock_ses_client):
        result = send_user_email(
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
        assert result is False
