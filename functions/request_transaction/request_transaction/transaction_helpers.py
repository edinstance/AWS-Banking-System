import uuid

from aws_lambda_powertools.event_handler.exceptions import BadRequestError


def is_valid_uuid(val: str) -> bool:
    """
    Check if the provided string is a valid UUID.
    
    Returns:
        True if the input is a non-empty string that can be parsed as a UUID; otherwise, False.
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
    Validate the presence and correctness of the 'Idempotency-Key' header in HTTP request headers.
    
    Raises a BadRequestError if the header is missing, not between 10 and 64 characters, or not a valid UUID.
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
