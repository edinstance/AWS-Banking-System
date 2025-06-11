import json
import uuid
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


def is_valid_uuid(val: str) -> bool:
    """
    Checks if the given string is a valid UUID.
    
    Returns True if the input is a non-empty string that can be parsed as a UUID; otherwise, returns False.
    """
    if not val or not isinstance(val, str):
        return False
    try:
        uuid.UUID(val)
        return True
    except ValueError:
        return False


def validate_request_headers(headers: dict) -> dict | None:
    """
    Validates the presence and format of the 'Idempotency-Key' header in HTTP request headers.
    
    If the header is missing, not within the required length (10–64 characters), or not a valid UUID, returns a 400 response dictionary with an error message and a suggested example. Returns None if the header is valid.
    
    Args:
        headers: Dictionary of HTTP request headers.
    
    Returns:
        A response dictionary with status 400 and error details if validation fails, or None if the header is valid.
    """
    idempotency_key = headers.get("idempotency-key")

    if not idempotency_key:
        suggested_key = str(uuid.uuid4())
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
        return create_response(
            400,
            {"error": "Idempotency-Key must be a valid UUID", "example": suggested_key},
            "OPTIONS,POST",
        )
    return None
