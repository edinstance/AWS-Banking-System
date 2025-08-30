import os
import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

from authentication.user_details import get_user_attributes
from ses import send_user_email_with_attachment, send_user_email

SES_NO_REPLY_EMAIL = os.environ.get("SES_NO_REPLY_EMAIL")
REPORTS_BUCKET = os.environ.get("REPORTS_BUCKET_NAME")
AWS_REGION = os.environ.get("AWS_REGION")
POWERTOOLS_LOG_LEVEL = os.environ.get("POWERTOOLS_LOG_LEVEL")
USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")

logger = Logger(service="MonthlyAccountReportsNotifyClient", level=POWERTOOLS_LOG_LEVEL)

s3 = boto3.client("s3", region_name=AWS_REGION)

# SES limit: 10 MB total, ~7 MB usable for attachments
MAX_ATTACHMENT_SIZE = 7 * 1024 * 1024  # 7 MB


def lambda_handler(event, _context: LambdaContext):
    logger.info(f"Received event: {event}")

    account_id = event["accountId"]
    user_id = event["userId"]
    statement_period = event["statementPeriod"]
    s3_key = f"{account_id}/{statement_period}.pdf"

    subject = f"Your Account Statement for {statement_period}"

    try:
        user_attributes = get_user_attributes(
            aws_region=AWS_REGION,
            logger=logger,
            username=user_id,
            user_pool_id=USER_POOL_ID,
        )

        recipient = user_attributes.get("email")
        user_name = user_attributes.get("name", "Customer")

        if not recipient:
            raise ValueError(f"User {user_id} has no email attribute in Cognito")

        # Get object metadata first (to check size without downloading the full file)
        head = s3.head_object(Bucket=REPORTS_BUCKET, Key=s3_key)
        file_size = head["ContentLength"]

        if file_size <= MAX_ATTACHMENT_SIZE:
            logger.info("PDF is small enough, sending as attachment")
            return send_report_as_attachment(recipient, user_name, subject, s3_key)
        else:
            logger.info("PDF too large, sending presigned URL")
            return send_report_as_link(recipient, user_name, subject, s3_key)

    except ClientError:
        logger.exception("Failed to fetch report from S3")
        raise
    except Exception:
        logger.exception("Exception processing email")
        raise


def send_report_as_attachment(
    recipient: str, user_name: str, subject: str, s3_key: str
):
    # Download PDF from S3
    pdf_obj = s3.get_object(Bucket=REPORTS_BUCKET, Key=s3_key)
    pdf_bytes = pdf_obj["Body"].read()

    body_text = f"Hello {user_name},\n\nPlease find your account statement attached.\n\nKind Regards."

    response = send_user_email_with_attachment(
        aws_region=AWS_REGION,
        logger=logger,
        sender_email=SES_NO_REPLY_EMAIL,
        to_addresses=[recipient],
        subject_data=subject,
        body_text=body_text,
        attachment_bytes=pdf_bytes,
        attachment_filename="statement.pdf",
    )

    return {
        "status": "success" if response else "failed",
        "messageId": response.get("MessageId") if response else None,
        "mode": "attachment",
    }


def send_report_as_link(recipient: str, user_name: str, subject: str, s3_key: str):
    presigned_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": REPORTS_BUCKET, "Key": s3_key},
        ExpiresIn=3600,  # 1 hour
    )

    body_text = (
        f"Hello {user_name},\n\n"
        f"Your account statement is ready.\n\n"
        f"Download it here (valid for 1 hour):\n{presigned_url}\n\n"
        f"If you need a new link please request one through the API.\n\n"
        f"Kind Regards."
    )

    response = send_user_email(
        aws_region=AWS_REGION,
        logger=logger,
        sender_email=SES_NO_REPLY_EMAIL,
        to_addresses=[recipient],
        subject_data=subject,
        text_body_data=body_text,
    )

    return {
        "status": "success" if response else "failed",
        "messageId": response.get("MessageId") if response else None,
        "mode": "link",
    }
