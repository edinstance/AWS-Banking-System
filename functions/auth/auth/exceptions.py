class AuthVerificationError(Exception):
    """Base exception for authentication verification failures."""

    pass


class AuthConfigurationError(AuthVerificationError):
    """Raised for issues with auth configuration (e.g., incorrect user pool ID, client ID)."""

    pass
