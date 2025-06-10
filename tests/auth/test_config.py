from functions.auth.auth.config import AuthConfig


class TestAuthConfig:

    def test_all_args(self):
        test_client_id = "explicit-client-id-123"
        test_user_pool_id = "explicit-user-pool-id-456"
        test_log_level = "DEBUG"

        config = AuthConfig(
            cognito_client_id=test_client_id,
            user_pool_id=test_user_pool_id,
            log_level=test_log_level,
        )

        assert config.cognito_client_id == test_client_id
        assert config.user_pool_id == test_user_pool_id
        assert config.log_level == test_log_level

    def test_env_args(self, monkeypatch):
        monkeypatch.setenv("COGNITO_CLIENT_ID", "env-client-id-789")
        monkeypatch.setenv("COGNITO_USER_POOL_ID", "env-user-pool-id-abc")
        monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "ERROR")

        config = AuthConfig(cognito_client_id=None, user_pool_id=None, log_level=None)

        assert config.cognito_client_id == "env-client-id-789"
        assert config.user_pool_id == "env-user-pool-id-abc"
        assert config.log_level == "ERROR"

    def test_default(self, monkeypatch):
        monkeypatch.delenv("COGNITO_CLIENT_ID", raising=False)
        monkeypatch.delenv("COGNITO_USER_POOL_ID", raising=False)
        monkeypatch.delenv("POWERTOOLS_LOG_LEVEL", raising=False)

        config = AuthConfig(cognito_client_id=None, user_pool_id=None, log_level="")

        assert config.cognito_client_id is None
        assert config.user_pool_id is None
        assert config.log_level == "INFO"
