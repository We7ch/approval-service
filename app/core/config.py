from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "approval-service")
    api_prefix: str = os.getenv("API_PREFIX", "/api/v1")
    environment: str = os.getenv("ENVIRONMENT", "local")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    enable_local_start_page: bool = env_flag("ENABLE_LOCAL_START_PAGE", False)
    local_start_page_file: str = os.getenv("LOCAL_START_PAGE_FILE", "./local_dev_home/index.html")

    def ensure_storage_paths(self) -> None:
        if self.database_url.startswith("sqlite:///./"):
            relative_path = self.database_url.removeprefix("sqlite:///./")
            Path(relative_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_storage_paths()
    return settings
