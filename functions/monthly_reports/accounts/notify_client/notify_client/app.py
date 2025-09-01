import json
import os

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import (
    APIGatewayRestResolver,
    CORSConfig,
)
from aws_lambda_powertools.event_handler.exceptions import (
    InternalServerError,
    UnauthorizedError,
    BadRequestError,
)
from aws_lambda_powertools.utilities.typing import LambdaContext

from authentication.authenticate_request import authenticate_request
from checks import check_user_owns_account
from dynamodb import get_dynamodb_resource
from s3 import get_s3_client
from .date_helpers import period_is_in_future
from .processing import process_report

SES_NO_REPLY_EMAIL = os.environ.get("SES_NO_REPLY_EMAIL")
REPORTS_BUCKET = os.environ.get("REPORTS_BUCKET")
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


@app.get("/accounts/<account_id>/reports/<statement_period>")
def get_account_report(account_id: str, statement_period: str):
    """
    Generate and return a monthly report for a given account and statement period.
    
    Authenticates the current API request, verifies the caller owns the specified account,
    validates the statement period is not in the future, and delegates report generation
    to the shared report processor.
    
    Parameters:
        account_id (str): ID of the account to generate the report for.
        statement_period (str): Statement period identifier (e.g. "2025-08").
    
    Returns:
        dict: Result returned by the report processor (contains report metadata and status).
    
    Raises:
        UnauthorizedError: If the request is not authenticated or the user does not own the account.
        BadRequestError: If the provided statement period is in the future.
        InternalServerError: On unexpected errors during processing.
    """
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

        if period_is_in_future(statement_period):
            raise BadRequestError("Statement period is in the future")

        result = process_report(
            account_id=account_id,
            user_id=user_id,
            statement_period=statement_period,
            cognito_user_pool_id=COGNITO_USER_POOL_ID,
            aws_region=AWS_REGION,
            reports_bucket=REPORTS_BUCKET,
            ses_no_reply_email=SES_NO_REPLY_EMAIL,
            max_attachment_size=MAX_ATTACHMENT_SIZE,
            logger=logger,
            s3_client=s3,
        )
        return result

    except UnauthorizedError:
        raise
    except Exception as e:
        logger.error(f"Error processing report: {e}", exc_info=True)
        raise InternalServerError("Internal server error")


@logger.inject_lambda_context
def lambda_handler(event, context: LambdaContext):
    """
    Lambda entrypoint that routes API Gateway HTTP requests to the APIGatewayRestResolver or handles direct (non-HTTP) invocations to generate an account report.
    
    For HTTP events (identified by presence of "httpMethod" or "requestContext") this delegates to app.resolve to handle authentication, authorisation and response formatting. For non-HTTP events it expects a JSON-like dict with keys "accountId", "userId" and "statementPeriod"; these are validated and passed to process_report. On validation failure a 400 response is returned. Any exception from report processing is caught and returned as a 500 response.
    
    Parameters:
        event (dict): The Lambda event. Either an API Gateway proxy event or a dict containing "accountId", "userId" and "statementPeriod".
        context (LambdaContext): Lambda runtime context (used to enrich logs with the request id).
    
    Returns:
        dict: An API Gateway-compatible response object (contains "statusCode" and JSON "body") or whatever app.resolve returns for HTTP requests.
    """
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
            result = process_report(
                account_id=account_id,
                user_id=user_id,
                statement_period=statement_period,
                cognito_user_pool_id=COGNITO_USER_POOL_ID,
                aws_region=AWS_REGION,
                reports_bucket=REPORTS_BUCKET,
                ses_no_reply_email=SES_NO_REPLY_EMAIL,
                max_attachment_size=MAX_ATTACHMENT_SIZE,
                logger=logger,
                s3_client=s3,
            )
            return result
        except Exception as e:
            logger.error(f"Error processing report: {e}", exc_info=True)
            return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
