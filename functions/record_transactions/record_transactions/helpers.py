import json
import uuid
from typing import Dict, Any


def create_response(
    status_code: int, body_dict: Dict[str, Any], methods: str
) -> Dict[str, Any]:
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
    Determines whether a provided string is a valid UUID.

    Args:
        val: The string to validate.

    Returns:
        True if the string is a valid UUID, otherwise False.
    """
    if not val or not isinstance(val, str):
        return False
    try:
        uuid.UUID(val)
        return True
    except ValueError:
        return False


def validate_request_headers(headers: dict) -> dict | None:
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
