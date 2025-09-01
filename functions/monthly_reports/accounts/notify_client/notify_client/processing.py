from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from authentication.user_details import get_user_attributes
from functions.monthly_reports.accounts.notify_client.notify_client.send_report import (
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
