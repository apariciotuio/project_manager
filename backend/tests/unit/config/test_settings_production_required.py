"""[RED] Startup validation: required secrets must be set in production."""
from __future__ import annotations

import pytest


class TestProductionRequiredSecrets:
    def test_production_missing_jwt_secret_raises(self) -> None:
        """In prod with jwt_secret = sentinel default → ConfigurationError."""
        from app.config.settings import AuthSettings
        from app.domain.errors.codes import ConfigurationError

        with pytest.raises(ConfigurationError) as exc_info:
            AuthSettings(
                APP_ENV="production",
                jwt_secret="change-me-in-prod-use-32-chars-or-more-please",
            )
        assert "jwt_secret" in str(exc_info.value).lower()

    def test_production_valid_jwt_secret_passes(self) -> None:
        """In prod with a real jwt_secret → no error."""
        from app.config.settings import AuthSettings

        # Should not raise — pass the field name directly (pydantic-settings init kwarg = field name)
        settings = AuthSettings(
            APP_ENV="production",
            jwt_secret="a-real-production-secret-that-is-long-enough-123",
        )
        assert settings.jwt_secret == "a-real-production-secret-that-is-long-enough-123"

    def test_dev_env_missing_jwt_secret_passes(self) -> None:
        """In dev, sentinel default is acceptable — no raise."""
        from app.config.settings import AuthSettings

        # Should not raise
        settings = AuthSettings(
            APP_ENV="development",
            jwt_secret="change-me-in-prod-use-32-chars-or-more-please",
        )
        assert settings.jwt_secret == "change-me-in-prod-use-32-chars-or-more-please"

    def test_production_missing_dundun_api_key_raises(self) -> None:
        """In prod with dundun api_key = dev-fake-key → ConfigurationError."""
        from app.config.settings import DundunSettings
        from app.domain.errors.codes import ConfigurationError

        with pytest.raises(ConfigurationError) as exc_info:
            DundunSettings(
                APP_ENV="production",
                api_key="dev-fake-key",
            )
        assert "api_key" in str(exc_info.value).lower()

    def test_error_message_includes_variable_name(self) -> None:
        """ConfigurationError message must contain the variable name."""
        from app.config.settings import AuthSettings
        from app.domain.errors.codes import ConfigurationError

        with pytest.raises(ConfigurationError) as exc_info:
            AuthSettings(
                APP_ENV="production",
                jwt_secret="change-me-in-prod-use-32-chars-or-more-please",
            )
        error_message = str(exc_info.value)
        # Must name the variable so ops can act immediately
        assert "jwt_secret" in error_message.lower() or "AUTH_JWT_SECRET" in error_message

    def test_production_missing_puppet_api_key_raises(self) -> None:
        """In prod with puppet api_key = dev-fake-key → ConfigurationError."""
        from app.config.settings import PuppetSettings
        from app.domain.errors.codes import ConfigurationError

        with pytest.raises(ConfigurationError) as exc_info:
            PuppetSettings(
                APP_ENV="production",
                api_key="dev-fake-key",
            )
        assert "api_key" in str(exc_info.value).lower()

    def test_production_missing_puppet_callback_secret_raises(self) -> None:
        """In prod with puppet callback_secret = dev-puppet-callback-secret → ConfigurationError."""
        from app.config.settings import PuppetSettings
        from app.domain.errors.codes import ConfigurationError

        with pytest.raises(ConfigurationError) as exc_info:
            PuppetSettings(
                APP_ENV="production",
                api_key="real-puppet-key",
                callback_secret="dev-puppet-callback-secret",
            )
        assert "callback_secret" in str(exc_info.value).lower()

    def test_production_valid_puppet_secrets_passes(self) -> None:
        """In prod with real puppet secrets → no error."""
        from app.config.settings import PuppetSettings

        settings = PuppetSettings(
            APP_ENV="production",
            api_key="real-puppet-key-123",
            callback_secret="real-puppet-callback-secret-456",
        )
        assert settings.api_key == "real-puppet-key-123"
        assert settings.callback_secret == "real-puppet-callback-secret-456"

    def test_dev_env_puppet_defaults_passes(self) -> None:
        """In dev, puppet sentinel defaults are acceptable."""
        from app.config.settings import PuppetSettings

        settings = PuppetSettings(
            APP_ENV="development",
            api_key="dev-fake-key",
            callback_secret="dev-puppet-callback-secret",
        )
        assert settings.api_key == "dev-fake-key"
        assert settings.callback_secret == "dev-puppet-callback-secret"
