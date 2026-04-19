import os
from dataclasses import dataclass


@dataclass
class Settings:
    app_name: str = "MiniShop"
    version: str = "0.9"

    secret_key: str = os.environ.get("MINISHOP_SECRET_KEY", "dev-secret-change-me")
    database_url: str = os.environ.get("MINISHOP_DATABASE_URL", "sqlite:///minishop.db")

    cors_origins: str = os.environ.get("MINISHOP_CORS_ORIGINS", "")

    debug: bool = os.environ.get("MINISHOP_DEBUG", "true").lower() == "true"


settings = Settings()