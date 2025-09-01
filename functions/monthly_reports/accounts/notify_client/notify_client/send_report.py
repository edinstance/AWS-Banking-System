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
