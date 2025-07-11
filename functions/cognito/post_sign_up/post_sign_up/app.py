import os

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from create import create_account_if_not_exists
from dynamodb import get_dynamodb_resource
from ses import send_user_email

ENVIRONMENT_NAME = os.environ.get("ENVIRONMENT_NAME", "dev")
POWERTOOLS_LOG_LEVEL = os.environ.get("POWERTOOLS_LOG_LEVEL", "INFO").upper()
ACCOUNTS_TABLE_NAME = os.environ.get("ACCOUNTS_TABLE_NAME")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")
SES_ENABLED = os.environ.get("SES_ENABLED", "FALSE").upper() == "TRUE"
SES_SENDER_EMAIL = os.environ.get("SES_SENDER_EMAIL")
SES_REPLY_EMAIL = os.environ.get("SES_REPLY_EMAIL")
SES_BOUNCE_EMAIL = os.environ.get("SES_BOUNCE_EMAIL")

logger = Logger(service="PostSignUp", level=POWERTOOLS_LOG_LEVEL)

dynamodb = get_dynamodb_resource(DYNAMODB_ENDPOINT, AWS_REGION, logger)
if ACCOUNTS_TABLE_NAME:
    table = dynamodb.Table(ACCOUNTS_TABLE_NAME)
    logger.debug(f"Initialized DynamoDB table: {ACCOUNTS_TABLE_NAME}")
else:
    logger.critical("FATAL: ACCOUNTS_TABLE_NAME environment variable not set!")
    table = None


@logger.inject_lambda_context
def lambda_handler(event, _context: LambdaContext):
    if not table:
        logger.error("DynamoDB table resource is not initialized")
        return event

    logger.info(f"Received event: {event}")

    try:
        username = event.get("userName")

        user_attributes = event.get("request", {}).get("userAttributes", {})
        user_email = user_attributes.get("email")

        account_id = create_account_if_not_exists(
            table=table, logger=logger, user_id=username
        )

        if SES_ENABLED:

            sender = SES_SENDER_EMAIL
            recipients = [user_email]
            subject = "Thank you for registering!"
            subject_charset = "UTF-8"
            text_body = (
                f"Thank you for signing up, here is your account ID: {account_id}"
            )
            html_body = f"""
                        <html>
                        <head></head>
                        <body>
                          <p>Thank you for signing up, here is your account ID: {account_id}</p>
                        </body>
                        </html>
                        """
            reply_to = [SES_REPLY_EMAIL]
            bounce_path = SES_BOUNCE_EMAIL
            tags_to_add = [
                {"Name": "Environment", "Value": ENVIRONMENT_NAME},
            ]

            email_sent_successfully = send_user_email(
                aws_region=AWS_REGION,
                logger=logger,
                sender_email=sender,
                to_addresses=recipients,
                subject_data=subject,
                subject_charset=subject_charset,
                text_body_data=text_body,
                html_body_data=html_body,
                reply_to_addresses=reply_to,
                return_path=bounce_path,
                tags=tags_to_add,
            )

            if not email_sent_successfully:
                logger.error("Email sending failed")
                raise Exception("Failed to send email")

            logger.info("Email sent successfully")

        return event

    except Exception as e:
        logger.error(f"Error in post signup handler: {str(e)}")
        raise e
