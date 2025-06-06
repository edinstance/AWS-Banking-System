import json

from aws_lambda_powertools.utilities.typing import LambdaContext

from .helpers import create_response
from .service import get_auth_service


def lambda_handler(event, context: LambdaContext):
    auth_service = get_auth_service()
    request_id = context.aws_request_id
    auth_service.logger.append_keys(request_id=request_id)
    auth_service.logger.info("Processing login/refresh proxy request.")

    if event["httpMethod"] == "OPTIONS":
        return create_response(200, {}, "POST")

    path = event.get("path")
    http_method = event.get("httpMethod")

    if http_method == "POST":
        try:
            request_body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError:
            auth_service.logger.warning("Invalid JSON in request body.")
            return create_response(
                400, {"error": "Invalid JSON format in request body"}, "POST"
            )

        if path == "/auth/login":
            return auth_service.handle_login(request_body)
        elif path == "/auth/refresh":
            return auth_service.handle_refresh(request_body)
        else:
            auth_service.logger.warning(f"Unsupported path: {path}")
            return create_response(404, {"error": "Not Found"}, "POST")
    else:
        auth_service.logger.warning(f"Unsupported HTTP method: {http_method}")
        return create_response(405, {"error": "Method Not Allowed"}, "POST")
