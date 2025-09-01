import json
from typing import List, Dict, Optional

import boto3
from aws_lambda_powertools import Logger
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText


def get_ses_client(aws_region: str, logger: Logger):
    """
    Initialise and return an AWS SES client for the specified region.
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
    Send a simple email (text and/or HTML) using AWS SES.
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
    Send an email with a single attachment using AWS SES (send_raw_email).
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
