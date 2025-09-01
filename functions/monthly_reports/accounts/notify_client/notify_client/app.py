import os
import json
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import (
    APIGatewayRestResolver,
    CORSConfig,
)
from aws_lambda_powertools.event_handler.exceptions import (
    InternalServerError,
    UnauthorizedError,
)
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

from authentication.authenticate_request import authenticate_request
from authentication.user_details import get_user_attributes
from checks import check_user_owns_account
from dynamodb import get_dynamodb_resource
from s3 import get_s3_client
from ses import send_user_email_with_attachment, send_user_email

SES_NO_REPLY_EMAIL = os.environ.get("SES_NO_REPLY_EMAIL")
REPORTS_BUCKET = os.environ.get("REPORTS_BUCKET_NAME")
AWS_REGION = os.environ.get("AWS_REGION")
POWERTOOLS_LOG_LEVEL = os.environ.get("POWERTOOLS_LOG_LEVEL")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
ACCOUNTS_TABLE_NAME = os.environ.get("ACCOUNTS_TABLE_NAME")

logger = Logger(service="MonthlyAccountReportsNotifyClient", level=POWERTOOLS_LOG_LEVEL)

s3 = get_s3_client(AWS_REGION, logger)

dynamodb = get_dynamodb_resource(DYNAMODB_ENDPOINT, AWS_REGION, logger)
if ACCOUNTS_TABLE_NAME:
    table = dynamodb.Table(ACCOUNTS_TABLE_NAME)
    logger.debug(f"Initialized DynamoDB table: {ACCOUNTS_TABLE_NAME}")
else:
    logger.critical("FATAL: ACCOUNTS_TABLE_NAME environment variable not set!")
    table = None

# SES limit: 10 MB total, ~7 MB usable for attachments
MAX_ATTACHMENT_SIZE = 7 * 1024 * 1024  # 7 MB

app = APIGatewayRestResolver(
    cors=CORSConfig(allow_headers=["Content-Type", "Authorization"])
)


def process_report(account_id: str, user_id: str, statement_period: str):
    s3_key = f"{account_id}/{statement_period}.pdf"
    subject = f"Your Account Statement for {statement_period}"

    try:
        user_attributes = get_user_attributes(
            aws_region=AWS_REGION,
            logger=logger,
            username=user_id,
            user_pool_id=COGNITO_USER_POOL_ID,
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


@app.get("/accounts/<account_id>/reports/<statement_period>")
def get_account_report(account_id: str, statement_period: str):
    try:
        event = app.current_event
        raw_headers = event.get("headers") or {}
        headers = {k.lower(): v for k, v in raw_headers.items()}

        user_id = authenticate_request(
            event,
            headers,
            COGNITO_USER_POOL_ID,
            COGNITO_CLIENT_ID,
            AWS_REGION.lower(),
            logger,
        )

        if not user_id:
            raise UnauthorizedError("Unauthorized")

        user_owns_account = check_user_owns_account(
            account_id=account_id, user_id=user_id, table=table
        )

        if not user_owns_account:
            raise UnauthorizedError("Unauthorized")

        result = process_report(account_id, user_id, statement_period)
        return result

    except UnauthorizedError:
        raise
    except Exception as e:
        logger.error(f"Error processing report: {e}", exc_info=True)
        raise InternalServerError("Internal server error")


@logger.inject_lambda_context
def lambda_handler(event, context: LambdaContext):
    logger.append_keys(request_id=context.aws_request_id)

    if "httpMethod" in event or "requestContext" in event:
        return app.resolve(event, context)
    else:
        account_id = event.get("accountId")
        user_id = event.get("userId")
        statement_period = event.get("statementPeriod")

        if not account_id or not user_id or not statement_period:
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {"error": "Missing accountId, userId, or statementPeriod"}
                ),
            }

        try:
            result = process_report(account_id, user_id, statement_period)
            return result
        except Exception as e:
            logger.error(f"Error processing report: {e}", exc_info=True)
            return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
