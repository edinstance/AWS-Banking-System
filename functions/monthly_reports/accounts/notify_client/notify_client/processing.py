from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from authentication.user_details import get_user_attributes
from .send_report import (
    send_report_as_attachment,
    send_report_as_link,
)


def process_report(
    account_id: str,
    user_id: str,
    statement_period: str,
    cognito_user_pool_id: str,
    aws_region: str,
    reports_bucket: str,
    max_attachment_size: int,
    ses_no_reply_email: str,
    logger: Logger,
    s3_client,
):
    """
    Process and send a monthly account statement to a user either as a PDF attachment or as a presigned link.

    Builds the S3 key for the requested statement, fetches the recipient's email and name from Cognito, checks the PDF size via S3 head_object and chooses between sending the file as an attachment (if size <= max_attachment_size) or sending a presigned URL. The function delegates actual email delivery to send_report_as_attachment or send_report_as_link and returns the result from that helper.

    Parameters:
        account_id: Account identifier used to construct the S3 key.
        user_id: Cognito username for the recipient.
        statement_period: Statement period string (used in S3 key and email subject).
        cognito_user_pool_id: Cognito user pool id to look up user attributes.
        aws_region: AWS region used for Cognito/S3 operations.
        reports_bucket: S3 bucket name where PDFs are stored.
        max_attachment_size: Maximum file size in bytes allowed for sending as an attachment.
        ses_no_reply_email: Sender (no-reply) email address used for SES.

    Returns:
        The return value from send_report_as_attachment or send_report_as_link (delegated delivery helper).

    Raises:
        botocore.exceptions.ClientError: If S3 head_object (or other AWS call) fails; this exception is logged and re-raised.
        Exception: Any other exception encountered while processing is logged and re-raised.
    """
    s3_key = f"{account_id}/{statement_period}.pdf"
    subject = f"Your Account Statement for {statement_period}"

    try:
        user_attributes = get_user_attributes(
            aws_region=aws_region,
            logger=logger,
            username=user_id,
            user_pool_id=cognito_user_pool_id,
        )

        recipient = user_attributes.get("email")
        user_name = user_attributes.get("name", "Customer")

        if not recipient:
            raise ValueError(f"User {user_id} has no email attribute in Cognito")

        # Get object metadata first (to check size without downloading the full file)
        head = s3_client.head_object(Bucket=reports_bucket, Key=s3_key)
        file_size = head["ContentLength"]

        if file_size <= max_attachment_size:
            logger.info("PDF is small enough, sending as attachment")
            return send_report_as_attachment(
                recipient=recipient,
                user_name=user_name,
                subject=subject,
                s3_key=s3_key,
                aws_region=aws_region,
                reports_bucket=reports_bucket,
                ses_no_reply_email=ses_no_reply_email,
                logger=logger,
                s3_client=s3_client,
            )
        else:
            logger.info("PDF too large, sending presigned URL")
            return send_report_as_link(
                recipient=recipient,
                user_name=user_name,
                subject=subject,
                s3_key=s3_key,
                aws_region=aws_region,
                reports_bucket=reports_bucket,
                ses_no_reply_email=ses_no_reply_email,
                logger=logger,
                s3_client=s3_client,
            )

    except ClientError:
        logger.exception("Failed to fetch report from S3")
        raise
    except Exception:
        logger.exception("Exception processing email")
        raise
