"""
Transaction Recording Lambda Function

This Lambda function records financial transactions in a DynamoDB table with
idempotency support to prevent duplicate transactions. It validates incoming
requests, processes transaction data, and stores it securely.

Environment Variables:
    TRANSACTIONS_TABLE_NAME: Name of the DynamoDB table for storing transactions
    ENVIRONMENT_NAME: Current deployment environment (dev, staging, prod)
    POWERTOOLS_LOG_LEVEL: Log level for Lambda Powertools logger
    IDEMPOTENCY_EXPIRATION_DAYS: Number of days to keep idempotency keys

Request Headers:
    Idempotency-Key: A unique identifier (preferably UUID v4) to prevent duplicate
                     transactions. The same key will return the same transaction
                     result if retried within 7 days.
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
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

from .auth import (
    authenticate_user,
)
from .dynamodb import get_dynamodb_resource
from .helpers import create_response, is_valid_uuid
from .transactions import (
    check_existing_transaction,
    validate_transaction_data,
    save_transaction,
)

TRANSACTIONS_TABLE_NAME = os.environ.get("TRANSACTIONS_TABLE_NAME")
ENVIRONMENT_NAME = os.environ.get("ENVIRONMENT_NAME", "dev")
POWERTOOLS_LOG_LEVEL = os.environ.get("POWERTOOLS_LOG_LEVEL", "INFO").upper()
IDEMPOTENCY_EXPIRATION_DAYS = int(os.environ.get("IDEMPOTENCY_EXPIRATION_DAYS", "7"))
VALID_TRANSACTION_TYPES = ["DEPOSIT", "WITHDRAWAL", "TRANSFER", "ADJUSTMENT"]
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID")

logger = Logger(service="RecordTransaction", level=POWERTOOLS_LOG_LEVEL)

dynamodb = get_dynamodb_resource(DYNAMODB_ENDPOINT, AWS_REGION, logger)
if TRANSACTIONS_TABLE_NAME:
    table = dynamodb.Table(TRANSACTIONS_TABLE_NAME)
    logger.debug(f"Initialized DynamoDB table: {TRANSACTIONS_TABLE_NAME}")
else:
    logger.critical("FATAL: TRANSACTIONS_TABLE_NAME environment variable not set!")
    table = None


@logger.inject_lambda_context
def lambda_handler(event, context: LambdaContext):
    """
    Handles incoming API Gateway requests to record financial transactions with idempotency.

    Validates the presence and format of the Idempotency-Key header, checks for duplicate transactions, validates and parses the request body, and stores new transactions in DynamoDB. Returns appropriate HTTP responses for validation errors, duplicate requests, and server errors.

    Args:
        event: The API Gateway event payload.
        context: The Lambda execution context.

    Returns:
        A dictionary formatted as an API Gateway HTTP response.
    """
    request_id = context.aws_request_id
    logger.append_keys(request_id=request_id)
    logger.info(f"Processing transaction request in {ENVIRONMENT_NAME} environment")

    if not table:
        logger.error("DynamoDB table resource is not initialized")
        return create_response(
            500, {"error": "Server configuration error"}, "OPTIONS,POST"
        )

    raw_headers = event.get("headers") or {}
    headers = {k.lower(): v for k, v in raw_headers.items()}

    user_id = authenticate_user(
        event, headers, COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, AWS_REGION.lower()
    )

    try:

        idempotency_key = headers.get("idempotency-key")
        if not idempotency_key:
            suggested_key = str(uuid.uuid4())
            logger.warning("Missing Idempotency-Key header")
            return create_response(
                400,
                {
                    "error": "Idempotency-Key header is required for transaction creation",
                    "suggestion": "Please include an Idempotency-Key header with a UUID v4 value",
                    "example": suggested_key,
                },
                "OPTIONS,POST",
            )

        idempotency_key = str(idempotency_key)
        if len(idempotency_key) < 10 or len(idempotency_key) > 64:
            suggested_key = str(uuid.uuid4())
            logger.warning(f"Invalid Idempotency-Key format: {idempotency_key}")
            return create_response(
                400,
                {
                    "error": "Idempotency-Key must be between 10 and 64 characters",
                    "suggestion": "We recommend using a UUID v4 format",
                    "example": suggested_key,
                },
                "OPTIONS,POST",
            )

        if not is_valid_uuid(idempotency_key):
            suggested_key = str(uuid.uuid4())
            logger.warning(f"Non-UUID Idempotency-Key used: {idempotency_key}")
            return create_response(
                400,
                {
                    "error": "Idempotency-Key must be a valid UUID",
                    "example": suggested_key,
                },
                "OPTIONS,POST",
            )

        try:
            existing_transaction = check_existing_transaction(
                idempotency_key, table, logger
            )
            if existing_transaction:
                logger.info(
                    f"Found existing transaction with ID: {existing_transaction.get('id')} for idempotency key {idempotency_key}"
                )
                return create_response(
                    201,
                    {
                        "message": "Transaction recorded successfully!",
                        "transactionId": existing_transaction["id"],
                        "idempotent": True,
                    },
                    "OPTIONS,POST",
                )
        except Exception as e:
            logger.error(f"Error checking idempotency: {str(e)}")
            return create_response(
                500,
                {"error": "Unable to verify transaction uniqueness. Please try again."},
                "OPTIONS,POST",
            )

        try:
            body_raw = event.get("body") or "{}"
            request_body = json.loads(body_raw)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in request body: {e}")
            return create_response(
                400, {"error": "Invalid JSON format in request body"}, "OPTIONS,POST"
            )

        is_valid, validation_error = validate_transaction_data(
            request_body, VALID_TRANSACTION_TYPES
        )
        if not is_valid:
            logger.warning(f"Validation error: {validation_error}")
            return create_response(400, {"error": validation_error}, "POST")

        account_id = request_body["accountId"]
        transaction_type = request_body["type"].upper()
        description = request_body.get("description", "")
        amount = Decimal(str(request_body["amount"]))

        transaction_id = str(uuid.uuid4())
        now_utc = datetime.now(timezone.utc)
        created_at_iso = now_utc.isoformat()

        ttl_datetime = now_utc + timedelta(days=365)
        ttl_timestamp = int(ttl_datetime.timestamp())

        idempotency_expiration = now_utc + timedelta(days=IDEMPOTENCY_EXPIRATION_DAYS)
        idempotency_expiration_timestamp = int(idempotency_expiration.timestamp())

        transaction_item = {
            "id": transaction_id,
            "createdAt": created_at_iso,
            "accountId": account_id,
            "userId": user_id,
            "amount": amount,
            "type": transaction_type,
            "description": description,
            "status": "COMPLETED",
            "ttlTimestamp": ttl_timestamp,
            "idempotencyKey": idempotency_key,
            "idempotencyExpiration": idempotency_expiration_timestamp,
            "environment": ENVIRONMENT_NAME,
            "requestId": request_id,
            "rawRequest": json.dumps(
                {
                    "accountId": account_id,
                    "userId": user_id,
                    "amount": str(amount),
                    "type": transaction_type,
                    "description": description,
                }
            ),
        }

        try:
            save_transaction(transaction_item, table, logger)
            logger.info(
                f"Successfully saved transaction {transaction_id} for user {user_id}"
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")

            if error_code == "ConditionalCheckFailedException":
                try:
                    existing_transaction = check_existing_transaction(
                        idempotency_key, table, logger
                    )
                    if existing_transaction:
                        return create_response(
                            409,
                            {
                                "error": "Transaction already processed",
                                "transactionId": existing_transaction["id"],
                                "idempotent": True,
                            },
                            "OPTIONS,POST",
                        )
                except Exception:
                    return create_response(
                        409,
                        {
                            "error": "Transaction already processed",
                            "idempotent": True,
                        },
                        "OPTIONS,POST",
                    )

            logger.error(
                f"Failed to save transaction {transaction_id}: {str(e)}", exc_info=True
            )

            return create_response(
                500,
                {"error": "Failed to process transaction. Please try again."},
                "OPTIONS,POST",
            )
        except Exception as e:
            logger.error(
                f"Failed to save transaction {transaction_id}: {str(e)}", exc_info=True
            )
            return create_response(
                500,
                {"error": "Failed to process transaction. Please try again."},
                "OPTIONS,POST",
            )

        response_payload = {
            "message": "Transaction recorded successfully!",
            "transactionId": transaction_id,
            "status": "COMPLETED",
            "timestamp": created_at_iso,
            "idempotencyKey": idempotency_key,
        }
        return create_response(201, response_payload, "OPTIONS,POST")

    except Exception as e:
        logger.exception(f"Unhandled exception in lambda_handler: {str(e)}")
        return create_response(
            500,
            {"error": "Internal server error. Please contact support."},
            "OPTIONS,POST",
        )
