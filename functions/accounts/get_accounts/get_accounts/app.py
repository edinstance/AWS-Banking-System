import os

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import (
    APIGatewayRestResolver,
    CORSConfig,
)
from aws_lambda_powertools.event_handler.exceptions import (
    InternalServerError,
    BadRequestError,
)
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

from authentication.authenticate_request import authenticate_request
from dynamodb import get_dynamodb_resource
from .getters import get_all_accounts, get_account_by_id

ACCOUNTS_TABLE_NAME = os.environ.get("ACCOUNTS_TABLE_NAME")
ENVIRONMENT_NAME = os.environ.get("ENVIRONMENT_NAME", "dev")
POWERTOOLS_LOG_LEVEL = os.environ.get("POWERTOOLS_LOG_LEVEL", "INFO").upper()
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID")

logger = Logger(service="GetTransactions", level=POWERTOOLS_LOG_LEVEL)
app = APIGatewayRestResolver(
    cors=CORSConfig(allow_headers=["Content-Type", "Authorization"])
)

dynamodb = get_dynamodb_resource(DYNAMODB_ENDPOINT, AWS_REGION, logger)
if ACCOUNTS_TABLE_NAME:
    table = dynamodb.Table(ACCOUNTS_TABLE_NAME)
    logger.debug(f"Initialized DynamoDB table: {ACCOUNTS_TABLE_NAME}")
else:
    logger.critical("FATAL: ACCOUNTS_TABLE_NAME environment variable not set!")
    table = None


@app.get("/accounts")
def get_accounts():
    user_id = authenticate_request(
        event=app.current_event,
        headers=app.current_event.headers,
        cognito_user_pool_id=COGNITO_USER_POOL_ID,
        cognito_client_id=COGNITO_CLIENT_ID,
        aws_region=AWS_REGION,
        logger=logger,
    )

    try:
        result = get_all_accounts(user_id, table, logger)
        logger.info(f"Successfully retrieved {len(result)} accounts")
        return result
    except ClientError as e:
        logger.error(f"Error getting accounts: {str(e)}")
        raise InternalServerError("Internal server error")


@app.get("/accounts/<account_id>")
def get_account(account_id):
    user_id = authenticate_request(
        event=app.current_event,
        headers=app.current_event.headers,
        cognito_user_pool_id=COGNITO_USER_POOL_ID,
        cognito_client_id=COGNITO_CLIENT_ID,
        aws_region=AWS_REGION,
        logger=logger,
    )

    try:
        result = get_account_by_id(user_id, account_id, table, logger)
        logger.info(f"Successfully retrieved account with id {account_id}")
        return result
    except ClientError as e:
        logger.error(f"Error getting account with id {account_id}: {str(e)}")
        raise InternalServerError("Internal server error")
    except ValueError as e:
        logger.error(f"Invalid account id: {str(e)}")
        raise BadRequestError("Invalid account id")


@logger.inject_lambda_context
def lambda_handler(event, context: LambdaContext):
    logger.append_keys(request_id=context.aws_request_id)
    logger.info(
        f"Processing account retrieval request in {ENVIRONMENT_NAME} environment via APIGatewayRestResolver."
    )

    if not table:
        logger.error("DynamoDB table resource is not initialized")
        raise InternalServerError("Server configuration error")

    return app.resolve(event, context)
