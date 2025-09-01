import os

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

from .exceptions import ReportGenerationError, ReportTemplateError, ReportUploadError
from s3 import get_s3_client
from .generate_pdf import generate_transactions_pdf

REPORTS_BUCKET = os.environ.get("REPORTS_BUCKET")
POWERTOOLS_LOG_LEVEL = os.environ.get("POWERTOOLS_LOG_LEVEL")
AWS_REGION = os.environ.get("AWS_REGION")

logger = Logger(service="CreateAccountsReport", level=POWERTOOLS_LOG_LEVEL)

s3 = get_s3_client(AWS_REGION, logger)


def lambda_handler(event, _context: LambdaContext):
    """
    Lambda handler that generates a transactions PDF for an account, uploads it to S3 and returns a presigned URL.

    The function expects `event` to contain the following keys: `accountId`, `userId`, `statementPeriod`, `transactions`, and `accountBalance`. It will:
    - validate the presence of required keys,
    - generate a PDF from the transactions,
    - upload the PDF to the S3 bucket configured by the REPORTS_BUCKET environment variable at key "<accountId>/<statementPeriod>.pdf",
    - create a presigned URL (expiry 3600s) for the uploaded object,
    - and return a dictionary with `reportUrl`, `accountId`, `userId` and `statementPeriod`.

    Parameters:
        event (dict): Event payload containing account and statement data. Required keys are listed above.
        _context (LambdaContext): AWS Lambda context object (not used).

    Returns:
        dict: {
            "reportUrl": str,         # presigned URL to download the PDF
            "accountId": str,
            "userId": str,
            "statementPeriod": str
        }

    Raises:
        ReportGenerationError: If required event fields are missing or PDF generation fails.
        ReportTemplateError: If the PDF template processing fails.
        ReportUploadError: If uploading to S3 or generating the presigned URL fails.
    """
    logger.info(f"Received event: {event}")

    try:
        required = [
            "accountId",
            "userId",
            "statementPeriod",
            "transactions",
            "accountBalance",
        ]
        missing = [k for k in required if k not in event]

        if missing:
            logger.error(f"Missing required fields: {missing}")
            raise ReportGenerationError(f"Invalid event: missing {missing}")

        # Generate PDF
        pdf_bytes = generate_transactions_pdf(event=event, logger=logger)

        logger.info("PDF generated successfully")

        # Store in S3
        s3_key = f"{event['accountId']}/{event['statementPeriod']}.pdf"
        try:
            s3.put_object(
                Bucket=REPORTS_BUCKET,
                Key=s3_key,
                Body=pdf_bytes,
                ContentType="application/pdf",
            )
        except ClientError as e:
            logger.exception("Failed to upload report to S3")
            raise ReportUploadError(f"S3 upload failed: {str(e)}") from e

        logger.info("Generating PDF uploaded to S3")

        try:
            presigned_url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": REPORTS_BUCKET, "Key": s3_key},
                ExpiresIn=3600,
            )
        except ClientError as e:
            logger.exception("Failed to generate presigned URL")
            raise ReportUploadError(f"Presigned URL generation failed: {str(e)}") from e

        logger.info("Presigned URL generated successfully")

        return {
            "reportUrl": presigned_url,
            "accountId": event["accountId"],
            "userId": event["userId"],
            "statementPeriod": event["statementPeriod"],
        }

    except (ReportGenerationError, ReportTemplateError, ReportUploadError):
        logger.exception("Report generation failed")
        raise
