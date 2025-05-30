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
from decimal import Decimal, DecimalException

import boto3
from aws_lambda_powertools import Logger
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# --- Configuration Constants ---
TRANSACTIONS_TABLE_NAME = os.environ.get("TRANSACTIONS_TABLE_NAME")
ENVIRONMENT_NAME = os.environ.get("ENVIRONMENT_NAME", "dev")
POWERTOOLS_LOG_LEVEL = os.environ.get("POWERTOOLS_LOG_LEVEL", "INFO").upper()
IDEMPOTENCY_EXPIRATION_DAYS = int(os.environ.get("IDEMPOTENCY_EXPIRATION_DAYS", "7"))
VALID_TRANSACTION_TYPES = ["DEPOSIT", "WITHDRAWAL", "TRANSFER", "ADJUSTMENT"]
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")

# --- Logger Setup using AWS Lambda Powertools ---
logger = Logger(service="RecordTransaction", level=POWERTOOLS_LOG_LEVEL)


def get_dynamodb_resource():
    """
    Returns a DynamoDB resource configured with a custom endpoint if specified.

    If a custom DynamoDB endpoint is set via environment variable, the resource is initialised with that endpoint; otherwise, the default AWS endpoint is used.
    """
    if DYNAMODB_ENDPOINT:
        logger.debug(f"Using custom DynamoDB endpoint: {DYNAMODB_ENDPOINT}")
        return boto3.resource(
            "dynamodb",
            endpoint_url=DYNAMODB_ENDPOINT,
            region_name=AWS_REGION,
        )
    logger.debug("Using default DynamoDB endpoint")
    return boto3.resource("dynamodb")


# Initialize DynamoDB resource and table
dynamodb = get_dynamodb_resource()
if TRANSACTIONS_TABLE_NAME:
    table = dynamodb.Table(TRANSACTIONS_TABLE_NAME)
    logger.debug(f"Initialized DynamoDB table: {TRANSACTIONS_TABLE_NAME}")
else:
    logger.critical("FATAL: TRANSACTIONS_TABLE_NAME environment variable not set!")
    table = None


def is_valid_uuid(val):
    """
    Determines whether the provided string is a valid UUID.

    Args:
        val: The string to validate.

    Returns:
        True if the string is a valid UUID, otherwise False.
    """
    try:
        uuid_obj = uuid.UUID(str(val))
        return str(uuid_obj) == val.lower()
    except (ValueError, AttributeError, TypeError):
        return False


def create_response(status_code, body_dict):
    """
    Constructs a standard HTTP response dictionary for API Gateway with JSON body and security headers.

    Args:
        status_code: The HTTP status code to return.
        body_dict: The response body as a dictionary to be serialised as JSON.

    Returns:
        A dictionary formatted for API Gateway responses, including headers and JSON body.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "X-Content-Type-Options": "nosniff",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        },
        "body": json.dumps(body_dict),
    }


def validate_transaction_data(data):
    """
    Validates transaction data against required fields and business rules.

    Checks for presence of required fields, valid transaction type, positive numeric amount, valid UUID for accountId, and ensures description is a string if provided.

    Args:
        data (dict): The transaction data to validate.

    Returns:
        tuple: A tuple (is_valid, error_message), where is_valid is True if the data is valid, otherwise False, and error_message contains the reason for invalidity or None if valid.
    """
    required_fields = ["accountId", "amount", "type"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"

    # Validate transaction type
    if data["type"].upper() not in VALID_TRANSACTION_TYPES:
        return (
            False,
            f"Invalid transaction type. Must be one of: {', '.join(VALID_TRANSACTION_TYPES)}",
        )

    # Validate amount format
    try:
        amount = Decimal(str(data["amount"]))
    except (ValueError, TypeError, DecimalException):
        return False, "Invalid amount format. Amount must be a number."

    # Validate amount is positive regardless of transaction type
    if amount <= 0:
        return False, "Amount must be a positive number"

    # Validate accountId format (assuming UUID format)
    if not is_valid_uuid(data["accountId"]):
        return False, "Invalid accountId, accountId must be a valid UUID"

    # Sanitize description to prevent injection
    if "description" in data and not isinstance(data["description"], str):
        return False, "Description must be a string"

    return True, None


def check_existing_transaction(idempotency_key):
    """
    Checks for an existing, non-expired transaction with the specified idempotency key.

    Queries the DynamoDB table using a secondary index to find a transaction matching the
    given idempotency key whose idempotency expiration timestamp is in the future.

    Args:
        idempotency_key: The idempotency key to search for.

    Returns:
        The existing transaction item as a dictionary if found and not expired; otherwise, None.

    Raises:
        ClientError: If a DynamoDB error occurs during the query.
    """
    try:
        response = table.query(
            IndexName="IdempotencyKeyIndex",
            KeyConditionExpression=Key("idempotencyKey").eq(idempotency_key),
            ConsistentRead=False,
        )

        items = response.get("Items", [])
        if items:
            now = int(datetime.now(timezone.utc).timestamp())
            for item in items:
                if item.get("idempotencyExpiration", 0) > now:
                    return item
        return None
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        logger.error(
            f"DynamoDB error checking idempotency: {error_code}", exc_info=True
        )
        if error_code == "ProvisionedThroughputExceededException":
            logger.warning("DynamoDB throughput exceeded during idempotency check")
        raise


def save_transaction(transaction_item):
    """
    Attempts to save a transaction record to DynamoDB, raising exceptions on failure.

    Args:
        transaction_item (dict): The transaction data to be stored.

    Returns:
        True if the transaction is saved successfully.

    Raises:
        Exception: If the operation fails due to throughput limits, missing resources, or other database errors.
    """
    try:
        table.put_item(Item=transaction_item)
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        logger.error(f"Failed to save transaction: {error_code}", exc_info=True)
        if error_code == "ProvisionedThroughputExceededException":
            raise Exception("Service temporarily unavailable due to high load") from e
        elif error_code == "ResourceNotFoundException":
            raise Exception("Transaction database configuration error") from e
        else:
            raise Exception(f"Database error: {error_code}") from e


@logger.inject_lambda_context
def lambda_handler(event, context):
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
        return create_response(500, {"error": "Server configuration error"})

    try:
        # Extract and normalize headers (case-insensitive)
        headers = {k.lower(): v for k, v in event.get("headers", {}).items()}

        # Validate idempotency key
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
            )

        # Sanitize and validate idempotency key
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
            )

        # Check if the idempotency key is a valid UUID
        if not is_valid_uuid(idempotency_key):
            suggested_key = str(uuid.uuid4())
            logger.warning(f"Non-UUID Idempotency-Key used: {idempotency_key}")
            return create_response(
                400,
                {
                    "error": "Idempotency-Key must be a valid UUID",
                    "example": suggested_key,
                },
            )

        # Check for existing transaction with this idempotency key
        try:
            existing_transaction = check_existing_transaction(idempotency_key)
            if existing_transaction:
                logger.info(
                    f"Found existing transaction with ID: {existing_transaction['id']}"
                )
                return create_response(
                    201,
                    {
                        "message": "Transaction recorded successfully!",
                        "transactionId": existing_transaction["id"],
                        "idempotent": True,  # Indicate this was an idempotent response
                    },
                )
        except Exception as e:
            logger.error(f"Error checking idempotency: {str(e)}")
            return create_response(
                500, {"error": "Unable to verify transaction uniqueness"}
            )

        # Parse and validate request body
        try:
            request_body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in request body: {e}")
            return create_response(
                400, {"error": "Invalid JSON format in request body"}
            )

        # Validate transaction data
        is_valid, validation_error = validate_transaction_data(request_body)
        if not is_valid:
            logger.warning(f"Validation error: {validation_error}")
            return create_response(400, {"error": validation_error})

        # Extract and process transaction data
        account_id = request_body.get("accountId")
        transaction_type = request_body.get("type").upper()
        description = request_body.get("description", "")
        amount = Decimal(str(request_body.get("amount")))

        # Generate transaction metadata
        transaction_id = str(uuid.uuid4())
        now_utc = datetime.now(timezone.utc)
        created_at_iso = now_utc.isoformat()

        # Calculate TTL values
        ttl_datetime = now_utc + timedelta(days=365)
        ttl_timestamp = int(ttl_datetime.timestamp())

        idempotency_expiration = now_utc + timedelta(days=IDEMPOTENCY_EXPIRATION_DAYS)
        idempotency_expiration_timestamp = int(idempotency_expiration.timestamp())

        # Prepare transaction record
        transaction_item = {
            "id": transaction_id,
            "createdAt": created_at_iso,
            "accountId": account_id,
            "amount": amount,  # Always store the positive amount
            "type": transaction_type,
            "description": description,
            "status": "COMPLETED",
            "ttlTimestamp": ttl_timestamp,
            "idempotencyKey": idempotency_key,
            "idempotencyExpiration": idempotency_expiration_timestamp,
            "environment": ENVIRONMENT_NAME,
            "requestId": request_id,
            # Store the sanitized version of the request.
            "rawRequest": json.dumps(
                {
                    "accountId": account_id,
                    "amount": str(amount),
                    "type": transaction_type,
                    "description": description,
                }
            ),
        }

        # Save transaction to DynamoDB
        try:
            save_transaction(transaction_item)
            logger.info(f"Successfully saved transaction {transaction_id}")
        except Exception as e:
            logger.error(f"Failed to save transaction: {str(e)}")
            return create_response(
                500, {"error": "Failed to process transaction. Please try again."}
            )

        # Return success response
        response_payload = {
            "message": "Transaction recorded successfully!",
            "transactionId": transaction_id,
            "status": "COMPLETED",
            "timestamp": created_at_iso,
            "idempotencyKey": idempotency_key,
        }
        return create_response(201, response_payload)

    except Exception as e:
        logger.exception(f"Unhandled exception: {str(e)}")
        return create_response(
            500, {"error": "Internal server error. Please contact support."}
        )
