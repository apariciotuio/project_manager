from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _csv_to_list(value: object) -> object:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    env: str = "dev"
    debug: bool = False
    log_level: str = "INFO"
    base_url: str = "http://localhost:17004"
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    _split_cors = field_validator("cors_allowed_origins", mode="before")(_csv_to_list)


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DATABASE_", env_file=".env", extra="ignore")

    url: str = "postgresql+asyncpg://wmp:wmp@localhost:17000/wmp"
    pool_size: int = 10
    max_overflow: int = 20


class CelerySettings(BaseSettings):
    """Celery config. Broker is Postgres via SQLAlchemy; final broker choice lands at M2."""

    model_config = SettingsConfigDict(env_prefix="CELERY_", env_file=".env", extra="ignore")

    broker_url: str = "sqla+postgresql+psycopg://wmp:wmp@localhost:17000/wmp"
    result_backend: str = "db+postgresql+psycopg://wmp:wmp@localhost:17000/wmp"
    task_always_eager: bool = True


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_", env_file=".env", extra="ignore")

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:17004/api/v1/auth/google/callback"
    jwt_secret: str = "change-me-in-prod-use-32-chars-or-more-please"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "wmp"
    jwt_audience: str = "wmp-web"
    jwt_expire_minutes: int = 60
    access_token_ttl_seconds: int = 900          # 15 min
    refresh_token_ttl_seconds: int = 2_592_000   # 30 days
    oauth_state_ttl_seconds: int = 300           # 5 min
    rate_limit_per_minute: int = 10              # slowapi: 10 req/min per IP on /auth/*
    allowed_domains: Annotated[list[str], NoDecode] = Field(default_factory=list)
    seed_superadmin_emails: Annotated[list[str], NoDecode] = Field(default_factory=list)

    _split_lists = field_validator(
        "allowed_domains", "seed_superadmin_emails", mode="before"
    )(_csv_to_list)


class DundunSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DUNDUN_", env_file=".env", extra="ignore")

    base_url: str = "http://localhost:17006"
    api_key: str = "dev-fake-key"
    use_fake: bool = True
    callback_url: str = "http://localhost:17004/api/v1/dundun/callback"


class PuppetSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PUPPET_", env_file=".env", extra="ignore")

    base_url: str = "http://localhost:17007"
    api_key: str = "dev-fake-key"
    use_fake: bool = True


class JiraSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JIRA_", env_file=".env", extra="ignore")

    base_url: str = ""
    encryption_key: str = ""


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env", extra="ignore")

    url: str = "redis://localhost:6379/0"
    template_cache_ttl_seconds: int = 300  # 5 minutes


class Settings:
    def __init__(self) -> None:
        self.app = AppSettings()
        self.database = DatabaseSettings()
        self.celery = CelerySettings()
        self.auth = AuthSettings()
        self.dundun = DundunSettings()
        self.puppet = PuppetSettings()
        self.jira = JiraSettings()
        self.redis = RedisSettings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
