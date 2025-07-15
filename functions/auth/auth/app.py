import json

from aws_lambda_powertools.utilities.typing import LambdaContext

from response_helpers import create_response
from .service import get_auth_service


def lambda_handler(event, context: LambdaContext):
    """
    AWS Lambda handler for processing authentication-related HTTP requests.

    Handles login and token refresh requests by delegating to the authentication service.
    Supports CORS preflight (OPTIONS) requests and returns appropriate HTTP responses for
    missing or unsupported methods and paths.

    Args:
        event: The Lambda event payload containing HTTP request details.
        context: The Lambda context object providing runtime information.

    Returns:
        A dictionary representing the HTTP response, including status code, headers, and body.
    """
    auth_service = get_auth_service()
    request_id = context.aws_request_id
    auth_service.logger.append_keys(request_id=request_id)
    auth_service.logger.info("Processing login/refresh proxy request.")

    http_method = event.get("httpMethod")
    path = event.get("path")

    if http_method is None:
        auth_service.logger.warning("Missing 'httpMethod' in event.")
        return create_response(
            400, {"error": "Bad Request: 'httpMethod' is missing."}, "OPTIONS,POST"
        )

    if http_method == "OPTIONS":
        return create_response(200, {}, "OPTIONS,POST")

    if http_method == "POST":
        try:
            body_raw = event.get("body") or "{}"
            request_body = json.loads(body_raw)
        except json.JSONDecodeError:
            auth_service.logger.warning("Invalid JSON in request body.")
            return create_response(
                400, {"error": "Invalid JSON format in request body"}, "OPTIONS,POST"
            )

        if path == "/auth/login":
            return auth_service.handle_login(request_body)
        if path == "/auth/refresh":
            return auth_service.handle_refresh(request_body)

        auth_service.logger.warning(f"Unsupported path: {path}")
        return create_response(404, {"error": "Not Found"}, "OPTIONS,POST")
    else:
        auth_service.logger.warning(f"Unsupported HTTP method: {http_method}")
        return create_response(405, {"error": "Method Not Allowed"}, "OPTIONS,POST")
