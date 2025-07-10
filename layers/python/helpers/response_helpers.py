import json
from typing import Dict, Any


def create_response(
    status_code: int, body_dict: Dict[str, Any], methods: str
) -> Dict[str, Any]:
    """
    Constructs a standardised HTTP response dictionary with JSON body and appropriate headers.

    Args:
        status_code: HTTP status code for the response.
        body_dict: Dictionary to be serialised as the JSON response body.
        methods: Comma-separated string of allowed HTTP methods for CORS.

    Returns:
        A dictionary representing the HTTP response, including status code, headers for content type, security, and CORS, and a JSON-encoded body.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "X-Content-Type-Options": "nosniff",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": methods,
            "Access-Control-Allow-Headers": "Content-Type, Authorization, Idempotency-Key",
        },
        "body": json.dumps(body_dict) if body_dict else "{}",
    }
