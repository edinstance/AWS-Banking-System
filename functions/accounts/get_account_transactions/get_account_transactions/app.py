import os
import json

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

from dynamodb import get_dynamodb_resource
from .exceptions import ValidationError
from .transaction_helpers import query_transactions

TRANSACTIONS_TABLE_NAME = os.environ.get("TRANSACTIONS_TABLE_NAME")
ENVIRONMENT_NAME = os.environ.get("ENVIRONMENT_NAME", "dev")
POWERTOOLS_LOG_LEVEL = os.environ.get("POWERTOOLS_LOG_LEVEL", "INFO").upper()
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")

logger = Logger(service="GetAccountTransactions", level=POWERTOOLS_LOG_LEVEL)

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


@app.get("/accounts/<account_id>/transactions")
def get_account_transactions(account_id: str):
    try:
        period = app.current_event.get_query_string_value("period", default_value=None)
        start = app.current_event.get_query_string_value("start", default_value=None)
        end = app.current_event.get_query_string_value("end", default_value=None)

        result = query_transactions(
            table=table,
            account_id=account_id,
            logger=logger,
            period=period,
            start=start,
            end=end,
        )
        return result

    except ValidationError as ve:
        logger.warning(f"Validation error: {ve}")
        raise BadRequestError(str(ve))
    except Exception as e:
        logger.error(f"Error fetching transactions: {e}", exc_info=True)
        raise InternalServerError("Internal server error")


@logger.inject_lambda_context
def lambda_handler(event, context: LambdaContext):
    logger.append_keys(request_id=context.aws_request_id)
    logger.info(f"Processing request in {ENVIRONMENT_NAME}")

    if not table:
        logger.error("DynamoDB table resource is not initialized")
        raise InternalServerError("Server configuration error")

    # Detect Step Functions or API Gateway
    if "httpMethod" in event or "requestContext" in event:
        return app.resolve(event, context)
    else:
        account_id = event.get("accountId")
        if not account_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing accountId"}),
            }

        try:
            result = query_transactions(
                table=table, account_id=account_id, logger=logger
            )

            response = {
                **event,
                "transactions": result.get("transactions", result),
            }

            return response

        except Exception as e:
            logger.error(f"Error fetching transactions: {e}", exc_info=True)
            return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
