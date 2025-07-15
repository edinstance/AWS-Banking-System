import json
from typing import Dict, Any


def create_response(
    status_code: int, body_dict: Dict[str, Any], methods: str
) -> Dict[str, Any]:
    """
    Generate a standard HTTP response dictionary with JSON body and headers for content type, security, and CORS.

    Parameters:
        status_code (int): The HTTP status code to return.
        body_dict (Dict[str, Any]): The response body to serialise as JSON.
        methods (str): Comma-separated list of allowed HTTP methods for CORS.

    Returns:
        Dict[str, Any]: A dictionary containing the status code, headers, and a JSON-encoded body suitable for HTTP responses.
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
