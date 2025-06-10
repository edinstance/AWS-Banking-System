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
        "body": json.dumps(body_dict),
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
