import os
from typing import Optional


class AuthConfig:
    def __init__(
        self,
        cognito_client_id: Optional[str] = None,
        user_pool_id: Optional[str] = None,
        log_level: Optional[str] = None,
    ):
        self.cognito_client_id = cognito_client_id or os.environ.get(
            "COGNITO_CLIENT_ID"
        )
        self.user_pool_id = user_pool_id or os.environ.get("COGNITO_USER_POOL_ID")

        self.log_level = (
            log_level or os.environ.get("POWERTOOLS_LOG_LEVEL", "INFO").upper()
        )
