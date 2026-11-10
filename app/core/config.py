import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_ADMIN_DATABASE = str(Path(__file__).resolve().parents[2] / "data" / "tourism-admin.sqlite3")


@dataclass(frozen=True)
class Settings:
    app_name: str = "Tourism Decision Support System API"
    environment: str = "local"
    api_prefix: str = "/api/v1"
    max_public_period_days: int = 366
    demo_dataset_version: str = "demo-2026-11-08-v1"
    admin_database: str = DEFAULT_ADMIN_DATABASE
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("TI_APP_NAME", "Tourism Decision Support System API"),
        environment=os.getenv("TI_ENVIRONMENT", "local"),
        api_prefix=os.getenv("TI_API_PREFIX", "/api/v1"),
        max_public_period_days=int(os.getenv("TI_MAX_PUBLIC_PERIOD_DAYS", "366")),
        demo_dataset_version=os.getenv("TI_DEMO_DATASET_VERSION", "demo-2026-11-08-v1"),
        admin_database=os.getenv("TI_ADMIN_DATABASE", DEFAULT_ADMIN_DATABASE),
        cors_origins=os.getenv("TI_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"),
    )
