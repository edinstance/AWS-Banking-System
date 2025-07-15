import json
from typing import List, Dict, Optional

import boto3
from aws_lambda_powertools import Logger


def get_ses_client(aws_region: str, logger: Logger):
    """
    Initialise and return an AWS SES client for the specified region.

    Raises:
        Exception: If the SES client cannot be initialised.
    """
    try:
        logger.info("Initialized SES client with default endpoint")
        return boto3.client("ses", region_name=aws_region)
    except Exception:
        logger.error("Failed to initialize SES client", exc_info=True)
        raise


def send_user_email(
    aws_region: str,
    logger: Logger,
    sender_email: str,
    to_addresses: List[str],
    subject_data: str,
    subject_charset: str,
    text_body_data: Optional[str] = None,
    text_body_charset: Optional[str] = None,
    html_body_data: Optional[str] = None,
    html_body_charset: Optional[str] = None,
    cc_addresses: Optional[List[str]] = None,
    bcc_addresses: Optional[List[str]] = None,
    reply_to_addresses: Optional[List[str]] = None,
    return_path: Optional[str] = None,
    tags: Optional[List[Dict[str, str]]] = None,
):
    """
    Send an email using AWS SES with configurable sender, recipients, subject, and body content.

    At least one of `text_body_data` or `html_body_data` must be provided. Supports optional CC, BCC, reply-to addresses, return path, and message tags. Returns `True` if the email is sent successfully, or `False` if sending fails or required body content is missing.

    Parameters:
        sender_email (str): The email address of the sender.
        to_addresses (List[str]): List of recipient email addresses.
        subject_data (str): The subject line of the email.
        subject_charset (str): Character set for the subject line.
        text_body_data (Optional[str]): Plain text content of the email body.
        text_body_charset (Optional[str]): Character set for the plain text body.
        html_body_data (Optional[str]): HTML content of the email body.
        html_body_charset (Optional[str]): Character set for the HTML body.
        cc_addresses (Optional[List[str]]): List of CC recipient email addresses.
        bcc_addresses (Optional[List[str]]): List of BCC recipient email addresses.
        reply_to_addresses (Optional[List[str]]): List of reply-to email addresses.
        return_path (Optional[str]): Email address for bounce and complaint notifications.
        tags (Optional[List[Dict[str, str]]]): List of tags to apply to the email.

    Returns:
        bool: True if the email was sent successfully, False otherwise.
    """
    ses_client = get_ses_client(aws_region=aws_region, logger=logger)

    message_body = {}
    if text_body_data:
        message_body["Text"] = {
            "Data": text_body_data,
            "Charset": text_body_charset if text_body_charset else "UTF-8",
        }
    if html_body_data:
        message_body["Html"] = {
            "Data": html_body_data,
            "Charset": html_body_charset if html_body_charset else "UTF-8",
        }

    if not message_body:
        logger.error("Email must contain at least a text or HTML body.")
        return False

    destination = {"ToAddresses": to_addresses}
    if cc_addresses:
        destination["CcAddresses"] = cc_addresses
    if bcc_addresses:
        destination["BccAddresses"] = bcc_addresses

    try:
        ses_client.send_email(
            Source=sender_email,
            Destination=destination,
            Message={
                "Subject": {
                    "Data": subject_data,
                    "Charset": subject_charset if subject_charset else "UTF-8",
                },
                "Body": message_body,
            },
            ReplyToAddresses=reply_to_addresses,
            ReturnPath=return_path,
            Tags=tags,
        )

        logger.info(f"Successfully sent email to users: {json.dumps(to_addresses)}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False
