import uuid

from response_helpers import create_response


def is_valid_uuid(val: str) -> bool:
    """
    Determine whether a given string is a valid UUID.

    Returns:
        bool: True if the input is a non-empty string that can be parsed as a UUID, otherwise False.
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
    normalized_headers = {k.lower(): v for k, v in headers.items()}
    idempotency_key = normalized_headers.get("idempotency-key")

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
