import uuid

from aws_lambda_powertools.event_handler.exceptions import BadRequestError


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


def validate_request_headers(headers: dict):
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
        raise BadRequestError(
            "Idempotency-Key header is required for transaction creation"
        )

    idempotency_key = str(idempotency_key)
    if len(idempotency_key) < 10 or len(idempotency_key) > 64:
        raise BadRequestError("Idempotency-Key must be between 10 and 64 characters")

    if not is_valid_uuid(idempotency_key):
        raise BadRequestError("Idempotency-Key must be a valid UUID")
    return None
