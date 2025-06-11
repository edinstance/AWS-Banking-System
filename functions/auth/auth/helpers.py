import json
from typing import Dict, Any


def create_response(
    status_code: int, body_dict: Dict[str, Any], methods: str
) -> Dict[str, Any]:
    """
    Constructs a standardised HTTP response dictionary with headers and JSON body.

    Args:
        status_code: HTTP status code for the response.
        body_dict: Dictionary to be serialised as the JSON response body.
        methods: Comma-separated string of allowed HTTP methods for CORS.

    Returns:
        A dictionary containing the status code, headers (including CORS and security headers), and a JSON-formatted body.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "X-Content-Type-Options": "nosniff",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": methods,
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": json.dumps(body_dict) if body_dict else "{}",
    }
