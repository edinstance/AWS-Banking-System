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
from .getters import get_all_transactions, get_transaction_by_id

TRANSACTIONS_TABLE_NAME = os.environ.get("TRANSACTIONS_TABLE_NAME")
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
if TRANSACTIONS_TABLE_NAME:
    table = dynamodb.Table(TRANSACTIONS_TABLE_NAME)
    logger.debug(f"Initialized DynamoDB table: {TRANSACTIONS_TABLE_NAME}")
else:
    logger.critical("FATAL: TRANSACTIONS_TABLE_NAME environment variable not set!")
    table = None


@app.get("/transactions")
def get_transactions():
    """
    Handles GET requests to retrieve all transactions for the authenticated user.
    
    Authenticates the request using Cognito credentials and returns a list of transactions associated with the user from the DynamoDB table. Raises an internal server error if the retrieval fails.
        
    Returns:
        list: A list of transaction records for the authenticated user.
    """
    user_id = authenticate_request(
        event=app.current_event,
        headers=app.current_event.headers,
        cognito_user_pool_id=COGNITO_USER_POOL_ID,
        cognito_client_id=COGNITO_CLIENT_ID,
        aws_region=AWS_REGION,
        logger=logger,
    )

    try:
        result = get_all_transactions(user_id, table, logger)
        logger.info(f"Successfully retrieved {len(result)} transactions")
        return result
    except ClientError as e:
        logger.error(f"Error getting transactions: {str(e)}")
        raise InternalServerError("Internal server error")


@app.get("/transactions/<transaction_id>")
def get_transaction(transaction_id):
    """
    Retrieve a specific transaction for the authenticated user by transaction ID.
    
    Authenticates the request using Cognito credentials and fetches the transaction with the given ID from DynamoDB. Returns the transaction data if found.
    
    Parameters:
        transaction_id (str): The unique identifier of the transaction to retrieve.
    
    Returns:
        dict: The transaction data corresponding to the provided transaction ID.
    
    Raises:
        InternalServerError: If there is an error accessing DynamoDB.
        BadRequestError: If the transaction ID is invalid.
    """
    user_id = authenticate_request(
        event=app.current_event,
        headers=app.current_event.headers,
        cognito_user_pool_id=COGNITO_USER_POOL_ID,
        cognito_client_id=COGNITO_CLIENT_ID,
        aws_region=AWS_REGION,
        logger=logger,
    )

    try:
        result = get_transaction_by_id(user_id, transaction_id, table, logger)
        logger.info(f"Successfully retrieved transaction with id {transaction_id}")
        return result
    except ClientError as e:
        logger.error(f"Error getting transaction with id {transaction_id}: {str(e)}")
        raise InternalServerError("Internal server error")
    except ValueError as e:
        logger.error(f"Invalid transaction id: {str(e)}")
        raise BadRequestError("Invalid transaction id")


@logger.inject_lambda_context
def lambda_handler(event, context: LambdaContext):
    """
    AWS Lambda entry point for handling API Gateway REST requests to retrieve transaction data.
    
    Initialises logging context with the AWS request ID, verifies DynamoDB table configuration, and delegates request processing to the APIGatewayRestResolver. Raises an InternalServerError if the DynamoDB table is not configured.
    """
    logger.append_keys(request_id=context.aws_request_id)
    logger.info(
        f"Processing transaction retrieval request in {ENVIRONMENT_NAME} environment via APIGatewayRestResolver."
    )

    if not table:
        logger.error("DynamoDB table resource is not initialized")
        raise InternalServerError("Server configuration error")

    return app.resolve(event, context)
