import json
from typing import List, Dict, Optional

import boto3
from aws_lambda_powertools import Logger


def get_ses_client(aws_region: str, logger: Logger):
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
