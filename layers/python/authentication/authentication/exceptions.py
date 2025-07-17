class AuthVerificationError(Exception):
    """Base exception for authentication verification failures."""

    pass


class MissingSubClaimError(AuthVerificationError):
    """Raised when the 'sub' claim is missing from a valid ID token."""

    pass


class InvalidTokenError(AuthVerificationError):
    """Raised for generic invalid token issues (e.g., malformed, expired, invalid signature)."""

    pass


class AuthConfigurationError(AuthVerificationError):
    """Raised for issues with auth configuration (e.g., incorrect user pool ID, client ID)."""

    pass
