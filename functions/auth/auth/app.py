from json import JSONDecodeError

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import (
    APIGatewayRestResolver,
    CORSConfig,
    content_types,
    Response,
)
from aws_lambda_powertools.utilities.typing import LambdaContext

from .service import get_auth_service

app = APIGatewayRestResolver(cors=CORSConfig())
logger = Logger()


@app.post("/auth/login")
def login():
    """Handle user login requests."""
    auth_service = get_auth_service()
    return auth_service.handle_login(app.current_event.json_body)


@app.post("/auth/refresh")
def refresh():
    """Handle token refresh requests."""
    auth_service = get_auth_service()
    return auth_service.handle_refresh(app.current_event.json_body)


@app.exception_handler(JSONDecodeError)
def handle_json_decode_error(exc: JSONDecodeError):
    """
    Handles JSONDecodeError, returning a 400 Bad Request with an error message.
    """
    logger.error(f"JSON decoding error: {exc}")
    return Response(
        status_code=400,
        content_type=content_types.APPLICATION_JSON,
        body="Invalid JSON format in request body.",
    )


def lambda_handler(event, context: LambdaContext):
    """
    AWS Lambda handler for processing authentication-related HTTP requests.

    Uses AWS Lambda Powertools APIGatewayRestResolver for streamlined HTTP handling.
    Automatically handles CORS, JSON parsing, and routing.

    Args:
        event: The Lambda event payload containing HTTP request details.
        context: The Lambda context object providing runtime information.

    Returns:
        A dictionary representing the HTTP response, including status code, headers, and body.
    """
    logger.append_keys(request_id=context.aws_request_id)
    logger.info("Processing authentication request via APIGatewayRestResolver.")

    return app.resolve(event, context)
