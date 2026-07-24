import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(key, default)


class Settings(BaseModel):
    discord_token: Optional[str] = Field(default_factory=lambda: get_env("DISCORD_TOKEN"))
    application_id: Optional[str] = Field(default_factory=lambda: get_env("APPLICATION_ID"))
    command_prefix: str = Field(default_factory=lambda: get_env("COMMAND_PREFIX", "!"))
    mongodb_uri: str = Field(default_factory=lambda: get_env("MONGODB_URI", "mongodb://localhost:27017"))
    mongodb_db: str = Field(default_factory=lambda: get_env("MONGODB_DB", "safenet"))
    redis_url: str = Field(default_factory=lambda: get_env("REDIS_URL", "redis://localhost:6379/0"))
    dashboard_host: str = Field(default_factory=lambda: get_env("DASHBOARD_HOST", "0.0.0.0"))
    dashboard_port: int = Field(default_factory=lambda: int(get_env("DASHBOARD_PORT", "8000")))
    dashboard_secret: str = Field(default_factory=lambda: get_env("DASHBOARD_SECRET", "change-me"))
    dashboard_username: str = Field(default_factory=lambda: get_env("DASHBOARD_USERNAME", "admin"))
    dashboard_password: str = Field(default_factory=lambda: get_env("DASHBOARD_PASSWORD", "change-me"))
    verification_role: str = Field(default_factory=lambda: get_env("VERIFICATION_ROLE", "Verified"))
    log_level: str = Field(default_factory=lambda: get_env("LOG_LEVEL", "INFO"))
    default_staff_role: str = Field(default_factory=lambda: get_env("DEFAULT_STAFF_ROLE", "Moderator"))
    default_mod_role: str = Field(default_factory=lambda: get_env("DEFAULT_MOD_ROLE", "Moderator"))


settings = Settings()
