import json
from typing import List, Dict, Optional

import boto3
from aws_lambda_powertools import Logger
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText


def get_ses_client(aws_region: str, logger: Logger):
    """
    Return an AWS SES client configured for the given AWS region.

    Parameters:
        aws_region (str): AWS region name (for example "eu-west-1") used to configure the SES client.

    Returns:
        botocore.client.BaseClient: A boto3 SES client instance configured for the specified region.

    Raises:
        Exception: Re-raises any exception raised while creating the client.
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
    subject_charset: str = "UTF-8",
    text_body_data: Optional[str] = None,
    text_body_charset: str = "UTF-8",
    html_body_data: Optional[str] = None,
    html_body_charset: str = "UTF-8",
    cc_addresses: Optional[List[str]] = None,
    bcc_addresses: Optional[List[str]] = None,
    reply_to_addresses: Optional[List[str]] = None,
    return_path: Optional[str] = None,
    tags: Optional[List[Dict[str, str]]] = None,
):
    """
    Send an email (plain text and/or HTML) via AWS Simple Email Service (SES).

    At least one of `text_body_data` or `html_body_data` must be provided; otherwise the function raises an Exception.
    Optional recipients in `cc_addresses` and `bcc_addresses` will be added to the destination. Optional fields
    `reply_to_addresses`, `return_path` and `tags` are included in the SES request when provided.

    Parameters:
        aws_region (str): AWS region name to create the SES client in.
        sender_email (str): The email address that appears as the sender (Source).
        to_addresses (List[str]): Primary recipient email addresses.
        subject_data (str): Email subject text (charset controlled by `subject_charset`).
        subject_charset (str): Charset for the subject (default "UTF-8").
        text_body_data (Optional[str]): Plain text body of the email.
        text_body_charset (str): Charset for the plain text body (default "UTF-8").
        html_body_data (Optional[str]): HTML body of the email.
        html_body_charset (str): Charset for the HTML body (default "UTF-8").
        cc_addresses (Optional[List[str]]): CC recipient addresses.
        bcc_addresses (Optional[List[str]]): BCC recipient addresses.
        reply_to_addresses (Optional[List[str]]): Reply-To addresses to include.
        return_path (Optional[str]): Return-Path address for bounce handling.
        tags (Optional[List[Dict[str, str]]]): List of tags (Name/Value dicts) to apply to the SES message.

    Returns:
        dict: The SES send_email response (includes 'MessageId' on success).

    Raises:
        Exception: If neither `text_body_data` nor `html_body_data` is provided.
        Exception: Re-raises exceptions from the SES client if the send operation fails.
    """
    ses_client = get_ses_client(aws_region=aws_region, logger=logger)

    message_body = {}
    if text_body_data:
        message_body["Text"] = {"Data": text_body_data, "Charset": text_body_charset}
    if html_body_data:
        message_body["Html"] = {"Data": html_body_data, "Charset": html_body_charset}

    if not message_body:
        logger.error("Email must contain at least a text or HTML body.")
        raise Exception("Email must contain at least a text or HTML body.")

    destination = {"ToAddresses": to_addresses}
    if cc_addresses:
        destination["CcAddresses"] = cc_addresses
    if bcc_addresses:
        destination["BccAddresses"] = bcc_addresses

    request_params = {
        "Source": sender_email,
        "Destination": destination,
        "Message": {
            "Subject": {"Data": subject_data, "Charset": subject_charset},
            "Body": message_body,
        },
    }

    if reply_to_addresses:
        request_params["ReplyToAddresses"] = reply_to_addresses
    if return_path:
        request_params["ReturnPath"] = return_path
    if tags:
        request_params["Tags"] = tags

    try:
        response = ses_client.send_email(**request_params)

        logger.info(
            f"Successfully sent email to {json.dumps(to_addresses)}, "
            f"MessageId={response['MessageId']}"
        )
        return response

    except Exception as e:
        logger.error(f"Failed to send email: {e}", exc_info=True)
        raise e


def send_user_email_with_attachment(
    aws_region: str,
    logger: Logger,
    sender_email: str,
    to_addresses: List[str],
    subject_data: str,
    body_text: str,
    attachment_bytes: bytes,
    attachment_filename: str,
    cc_addresses: Optional[List[str]] = None,
    bcc_addresses: Optional[List[str]] = None,
):
    """
    Send an email with a single attachment via AWS SES using send_raw_email.

    Constructs a multipart MIME message with a plain-text body and one attachment, sets To/Cc/Bcc headers,
    and sends the raw message through SES. Cc and Bcc recipients (if provided) are added to the SES
    Destinations list so they receive the message.

    Parameters:
        attachment_bytes (bytes): Raw bytes of the attachment to include.
        attachment_filename (str): Filename used in the attachment's Content-Disposition header.

    Returns:
        dict: The SES send_raw_email response (contains 'MessageId' on success).

    Raises:
        Exception: Re-raises any exception from the SES client on failure.
    """
    ses_client = get_ses_client(aws_region=aws_region, logger=logger)

    msg = MIMEMultipart()
    msg["Subject"] = subject_data
    msg["From"] = sender_email
    msg["To"] = ", ".join(to_addresses)
    if cc_addresses:
        msg["Cc"] = ", ".join(cc_addresses)
    if bcc_addresses:
        msg["Bcc"] = ", ".join(bcc_addresses)

    # Attach plain text body
    msg.attach(MIMEText(body_text, "plain"))

    # Attach the file
    part = MIMEApplication(attachment_bytes)
    part.add_header("Content-Disposition", "attachment", filename=attachment_filename)
    msg.attach(part)

    try:
        destinations = list(to_addresses)
        if cc_addresses:
            destinations.extend(cc_addresses)
        if bcc_addresses:
            destinations.extend(bcc_addresses)

        response = ses_client.send_raw_email(
            Source=sender_email,
            Destinations=destinations,
            RawMessage={"Data": msg.as_string()},
        )

        logger.info(
            f"Successfully sent email with attachment to {json.dumps(to_addresses)}, "
            f"MessageId={response['MessageId']}"
        )
        return response

    except Exception as e:
        logger.error(f"Failed to send email with attachment: {e}", exc_info=True)
        raise e
