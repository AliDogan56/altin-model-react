import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    environment: str
    database_path: Path
    model_dir: Path
    cors_origins: tuple[str, ...]
    auto_train: bool
    collection_interval_seconds: int
    retrain_minimum_rows: int
    retrain_every_new_rows: int
    gateway_url: str


def get_settings() -> Settings:
    environment = os.getenv("APP_ENV", "localhost").lower()
    aliases = {"local": "localhost", "dev": "development", "prod": "production"}
    environment = aliases.get(environment, environment)
    if environment not in {"localhost", "development", "production"}:
        raise RuntimeError("APP_ENV localhost, development veya production olmalıdır")
    defaults = {
        "localhost": (ROOT.parent / "data" / "gold_platform_localhost.sqlite3", ("http://127.0.0.1:8000", "http://localhost:8000"), True),
        "development": (ROOT.parent / "data" / "gold_platform_development.sqlite3", ("https://api-dev.example.com",), True),
        "production": (ROOT.parent / "data" / "gold_platform_production.sqlite3", ("https://app.example.com",), True),
    }
    db_default, origins_default, auto_default = defaults[environment]
    origins = tuple(x.strip() for x in os.getenv("CORS_ORIGINS", ",".join(origins_default)).split(",") if x.strip())
    return Settings(environment, Path(os.getenv("DATABASE_PATH", db_default)), Path(os.getenv("MODEL_DIR", ROOT / "models")), origins,
                    os.getenv("AUTO_TRAIN", str(auto_default)).lower() == "true",
                    int(os.getenv("COLLECTION_INTERVAL_SECONDS", "3600")), int(os.getenv("RETRAIN_MINIMUM_ROWS", "80")),
                    int(os.getenv("RETRAIN_EVERY_NEW_ROWS", "20")), os.getenv("GATEWAY_URL", "http://127.0.0.1:8000").rstrip("/"))


settings = get_settings()
