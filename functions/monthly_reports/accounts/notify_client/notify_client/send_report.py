from aws_lambda_powertools import Logger

from ses import send_user_email, send_user_email_with_attachment


def send_report_as_attachment(
    recipient: str,
    user_name: str,
    subject: str,
    s3_key: str,
    aws_region: str,
    reports_bucket: str,
    ses_no_reply_email: str,
    logger: Logger,
    s3_client,
):
    # Download PDF from S3
    """
    Send a PDF report downloaded from S3 to a recipient as an email attachment.

    Downloads the object at `s3_key` from `reports_bucket`, sends it as a file named "statement.pdf" using the configured SES sender, and returns a summary of the send attempt. Exceptions from S3 or SES calls are propagated.

    Parameters:
        s3_key (str): S3 object key of the PDF to attach.
        aws_region (str): AWS region used for the SES call.
        reports_bucket (str): Name of the S3 bucket containing the report.
        ses_no_reply_email (str): Sender email address to use for SES.

    Returns:
        dict: {
            "status": "success" | "failed",
            "messageId": str | None,
            "mode": "attachment"
        } — `status` is "success" if an SES response was received, `messageId` is taken from the SES response when available.
    """
    pdf_obj = s3_client.get_object(Bucket=reports_bucket, Key=s3_key)
    pdf_bytes = pdf_obj["Body"].read()

    body_text = f"Hello {user_name},\n\nPlease find your account statement attached.\n\nKind Regards."

    response = send_user_email_with_attachment(
        aws_region=aws_region,
        logger=logger,
        sender_email=ses_no_reply_email,
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


def send_report_as_link(
    recipient: str,
    user_name: str,
    subject: str,
    s3_key: str,
    aws_region: str,
    reports_bucket: str,
    ses_no_reply_email: str,
    logger: Logger,
    s3_client,
):
    """
    Send an email to a recipient containing a 1‑hour presigned S3 link to a report.

    Generates a presigned URL for the S3 object identified by `s3_key` in `reports_bucket` (valid for 3600 seconds), composes a short personalised message to `user_name` that includes the link, and sends it to `recipient` using the provided SES sender address. Returns a dictionary summarising the send result.

    Parameters:
        recipient (str): Recipient email address.
        user_name (str): Recipient's display name used in the message greeting.
        subject (str): Email subject line.
        s3_key (str): S3 object key for the report (path to the PDF in the bucket).
        aws_region (str): AWS region to use when sending the email.
        reports_bucket (str): Name of the S3 bucket containing the report.
        ses_no_reply_email (str): SES sender email address.

    Returns:
        dict: {
            "status": "success" if sending returned a truthy response otherwise "failed",
            "messageId": MessageId from the SES response if present else None,
            "mode": "link"
        }
    """
    presigned_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": reports_bucket, "Key": s3_key},
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
        aws_region=aws_region,
        logger=logger,
        sender_email=ses_no_reply_email,
        to_addresses=[recipient],
        subject_data=subject,
        text_body_data=body_text,
    )

    return {
        "status": "success" if response else "failed",
        "messageId": response.get("MessageId") if response else None,
        "mode": "link",
    }
