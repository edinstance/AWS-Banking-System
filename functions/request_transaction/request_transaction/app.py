"""
Transaction Requesting Lambda Function

This Lambda function requests financial transactions in a DynamoDB table with
idempotency support to prevent duplicate transactions. It validates incoming
requests, processes transaction data, and stores it securely.

Environment Variables:
    TRANSACTIONS_TABLE_NAME: Name of the DynamoDB table for storing transactions
    ENVIRONMENT_NAME: Current deployment environment (dev, staging, prod)
    POWERTOOLS_LOG_LEVEL: Log level for Lambda Powertools logger

Request Headers:
    Idempotency-Key: A unique identifier (preferably UUID v4) to prevent duplicate
                     transactions. The same key will return the same transaction
                     result if retried. Items automatically expire after 1 year via TTL.
                     Example: "123e4567-e89b-12d3-a456-426614174000"

Request Format:
    {
        "accountId": "account-123",
        "amount": 100.50,
        "type": "DEPOSIT",
        "description": "Deposit from checking account"
    }

Response Format:
    {
        "message": "Transaction recorded successfully!",
        "transactionId": "uuid-of-transaction"
    }
"""

import json
import os
import uuid

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
from .idempotency import handle_idempotency_error
from .transaction_helpers import validate_request_headers
from .transactions import (
    validate_transaction_data,
    save_transaction,
    build_transaction_item,
)

TRANSACTIONS_TABLE_NAME = os.environ.get("TRANSACTIONS_TABLE_NAME")
ENVIRONMENT_NAME = os.environ.get("ENVIRONMENT_NAME", "dev")
POWERTOOLS_LOG_LEVEL = os.environ.get("POWERTOOLS_LOG_LEVEL", "INFO").upper()
VALID_TRANSACTION_TYPES = ["DEPOSIT", "WITHDRAWAL"]
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID")

logger = Logger(service="RecordTransaction", level=POWERTOOLS_LOG_LEVEL)
app = APIGatewayRestResolver(
    cors=CORSConfig(allow_headers=["Content-Type", "Authorization", "Idempotency-Key"])
)

dynamodb = get_dynamodb_resource(DYNAMODB_ENDPOINT, AWS_REGION, logger)
if TRANSACTIONS_TABLE_NAME:
    table = dynamodb.Table(TRANSACTIONS_TABLE_NAME)
    logger.debug(f"Initialized DynamoDB table: {TRANSACTIONS_TABLE_NAME}")
else:
    logger.critical("FATAL: TRANSACTIONS_TABLE_NAME environment variable not set!")
    table = None


@app.post("/transactions")
def request_transaction():
    """Handle transaction request."""
    if not table:
        logger.error("DynamoDB table resource is not initialized")
        raise InternalServerError("Server configuration error")

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

    validate_request_headers(headers)

    idempotency_key = headers["idempotency-key"]
    request_id = event.request_context.request_id

    try:
        request_body = event.json_body
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in request body: {e}")
        raise BadRequestError("Invalid JSON format in request body")

    is_valid, validation_error = validate_transaction_data(
        request_body, VALID_TRANSACTION_TYPES
    )

    if not is_valid:
        logger.warning(f"Validation error: {validation_error}")
        raise BadRequestError(validation_error)

    transaction_id = str(uuid.uuid4())
    transaction_item = build_transaction_item(
        transaction_id,
        request_body,
        user_id,
        idempotency_key,
        request_id,
    )

    try:
        save_transaction(transaction_item, table, logger)
        logger.info(
            f"Successfully saved transaction {transaction_id} for user {user_id}"
        )
    except ClientError as e:
        try:
            error_response = handle_idempotency_error(
                idempotency_key, table, logger, transaction_id, e
            )
            if isinstance(error_response, tuple):
                return error_response
            else:
                return error_response
        except Exception as idempotency_error:
            logger.error(
                f"Error handling idempotency: {idempotency_error}", exc_info=True
            )
            raise idempotency_error
    except Exception as e:
        logger.error(
            f"Failed to save transaction {transaction_id}: {str(e)}", exc_info=True
        )
        raise InternalServerError(
            "Failed to process transaction. Please try again.",
        )

    response_payload = {
        "message": "Transaction requested successfully!",
        "transactionId": transaction_id,
        "status": "REQUESTED",
        "timestamp": transaction_item["createdAt"],
        "idempotencyKey": idempotency_key,
    }
    return response_payload, 201


@logger.inject_lambda_context
def lambda_handler(event, context: LambdaContext):
    """
    AWS Lambda handler for processing transaction-related HTTP requests.

    Uses AWS Lambda Powertools APIGatewayRestResolver for streamlined HTTP handling.
    Automatically handles CORS, JSON parsing, and routing.

    Args:
        event: The Lambda event payload containing HTTP request details.
        context: The Lambda context object providing runtime information.

    Returns:
        A dictionary representing the HTTP response, including status code, headers, and body.
    """
    logger.append_keys(request_id=context.aws_request_id)
    logger.info(
        f"Processing transaction request in {ENVIRONMENT_NAME} environment via APIGatewayRestResolver."
    )

    return app.resolve(event, context)
