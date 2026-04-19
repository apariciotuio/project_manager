from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_PRODUCTION_ENVS = frozenset({"production", "prod"})


def _csv_to_list(value: object) -> object:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


def _csv_to_kv_dict(value: object) -> object:
    """Parse 'key=value,key2=value2' string into {key: value, ...} dict."""
    if isinstance(value, str):
        if not value.strip():
            return {}
        result: dict[str, str] = {}
        for pair in value.split(","):
            pair = pair.strip()
            if not pair:
                continue
            eq_idx = pair.index("=")
            k = pair[:eq_idx].strip()
            v = pair[eq_idx + 1:].strip()
            result[k] = v
        return result
    return value


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    env: str = "dev"
    debug: bool = False
    log_level: str = "INFO"
    base_url: str = "http://localhost:17004"
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    max_body_bytes: int = 1_048_576
    csp_overrides: Annotated[dict[str, str], NoDecode] = Field(default_factory=dict)

    _split_cors = field_validator("cors_allowed_origins", mode="before")(_csv_to_list)
    _split_csp = field_validator("csp_overrides", mode="before")(_csv_to_kv_dict)

    @model_validator(mode="after")
    def _validate_cors_in_production(self) -> "AppSettings":
        """EP-12: in production, APP_CORS_ALLOWED_ORIGINS must be explicit.

        An empty list would otherwise fall through with no origins accepted,
        breaking browser clients at startup. The CORSPolicyMiddleware already
        rejects '*' in prod; this closes the reciprocal gap (empty origin
        list in non-dev is a misconfiguration, not a valid default).
        """
        if self.env.lower() not in _PRODUCTION_ENVS:
            return self
        from app.domain.errors.codes import ConfigurationError  # deferred — avoid circular
        if not self.cors_allowed_origins:
            raise ConfigurationError("cors_allowed_origins")
        return self


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DATABASE_", env_file=".env", extra="ignore")

    url: str = "postgresql+asyncpg://wmp:wmp@localhost:17000/wmp"
    pool_size: int = 10
    max_overflow: int = 20


_AUTH_JWT_SECRET_SENTINEL = "change-me-in-prod-use-32-chars-or-more-please"


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_", env_file=".env", extra="ignore")

    # Read APP_ENV without the AUTH_ prefix via alias
    app_env: str = Field(default="dev", alias="APP_ENV")

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:17004/api/v1/auth/google/callback"
    jwt_secret: str = _AUTH_JWT_SECRET_SENTINEL
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "wmp"
    jwt_audience: str = "wmp-web"
    jwt_expire_minutes: int = 60
    access_token_ttl_seconds: int = 900          # 15 min — override per env for DX (see .env.development)
    refresh_token_ttl_seconds: int = 2_592_000   # 30 days
    oauth_state_ttl_seconds: int = 300           # 5 min
    rate_limit_per_minute: int = 10              # slowapi: 10 req/min per IP on /auth/* (override for CI/dev)
    allowed_domains: Annotated[list[str], NoDecode] = Field(default_factory=list)
    seed_superadmin_emails: Annotated[list[str], NoDecode] = Field(default_factory=list)

    _split_lists = field_validator(
        "allowed_domains", "seed_superadmin_emails", mode="before"
    )(_csv_to_list)

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "AuthSettings":
        if self.app_env.lower() not in _PRODUCTION_ENVS:
            return self
        from app.domain.errors.codes import ConfigurationError  # deferred — avoids circular at module load
        if self.jwt_secret == _AUTH_JWT_SECRET_SENTINEL:
            raise ConfigurationError("jwt_secret")
        return self


_DUNDUN_API_KEY_SENTINEL = "dev-fake-key"
_DUNDUN_CALLBACK_SECRET_SENTINEL = "dev-callback-secret"
_DUNDUN_SERVICE_KEY_SENTINEL = "dev-service-key"


class DundunSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DUNDUN_", env_file=".env", extra="ignore")

    app_env: str = Field(default="dev", alias="APP_ENV")

    base_url: str = "http://localhost:17006"
    api_key: str = _DUNDUN_API_KEY_SENTINEL
    service_key: str = _DUNDUN_SERVICE_KEY_SENTINEL
    use_fake: bool = True
    callback_url: str = "http://localhost:17004/api/v1/dundun/callback"
    callback_secret: str = _DUNDUN_CALLBACK_SECRET_SENTINEL
    http_timeout: float = 30.0

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "DundunSettings":
        if self.app_env.lower() not in _PRODUCTION_ENVS:
            return self
        from app.domain.errors.codes import ConfigurationError
        if self.api_key == _DUNDUN_API_KEY_SENTINEL:
            raise ConfigurationError("api_key")
        if self.callback_secret == _DUNDUN_CALLBACK_SECRET_SENTINEL:
            raise ConfigurationError("callback_secret")
        if self.service_key == _DUNDUN_SERVICE_KEY_SENTINEL:
            raise ConfigurationError("service_key")
        return self


_PUPPET_API_KEY_SENTINEL = "dev-fake-key"
_PUPPET_CALLBACK_SECRET_SENTINEL = "dev-puppet-callback-secret"
_PUPPET_SERVICE_KEY_SENTINEL = "dev-service-key"


class PuppetSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PUPPET_", env_file=".env", extra="ignore")

    app_env: str = Field(default="dev", alias="APP_ENV")

    base_url: str = "http://localhost:17007"
    api_key: str = _PUPPET_API_KEY_SENTINEL
    service_key: str = _PUPPET_SERVICE_KEY_SENTINEL
    callback_secret: str = _PUPPET_CALLBACK_SECRET_SENTINEL
    use_fake: bool = True

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "PuppetSettings":
        if self.app_env.lower() not in _PRODUCTION_ENVS:
            return self
        from app.domain.errors.codes import ConfigurationError
        if self.api_key == _PUPPET_API_KEY_SENTINEL:
            raise ConfigurationError("api_key")
        if self.callback_secret == _PUPPET_CALLBACK_SECRET_SENTINEL:
            raise ConfigurationError("callback_secret")
        if self.service_key == _PUPPET_SERVICE_KEY_SENTINEL:
            raise ConfigurationError("service_key")
        return self


_JIRA_API_TOKEN_SENTINEL = "dev-jira-token"


class JiraSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JIRA_", env_file=".env", extra="ignore")

    app_env: str = Field(default="dev", alias="APP_ENV")

    base_url: str = ""
    email: str = ""
    api_token: SecretStr = SecretStr(_JIRA_API_TOKEN_SENTINEL)
    encryption_key: str = ""

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "JiraSettings":
        if self.app_env.lower() not in _PRODUCTION_ENVS:
            return self
        from app.domain.errors.codes import ConfigurationError
        if self.api_token.get_secret_value() == _JIRA_API_TOKEN_SENTINEL:
            raise ConfigurationError("jira.api_token")
        return self


_MCP_TOKEN_PEPPER_SENTINEL = "dev-mcp-pepper-change-me-in-prod-32chars"


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_", env_file=".env", extra="ignore")

    app_env: str = Field(default="dev", alias="APP_ENV")

    token_pepper: str = _MCP_TOKEN_PEPPER_SENTINEL

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "MCPSettings":
        if self.app_env.lower() not in _PRODUCTION_ENVS:
            return self
        from app.domain.errors.codes import ConfigurationError
        if self.token_pepper == _MCP_TOKEN_PEPPER_SENTINEL:
            raise ConfigurationError("mcp.token_pepper")
        return self


class Settings:
    def __init__(self) -> None:
        self.app = AppSettings()
        self.database = DatabaseSettings()
        self.auth = AuthSettings()
        self.dundun = DundunSettings()
        self.puppet = PuppetSettings()
        self.jira = JiraSettings()
        self.mcp = MCPSettings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
