import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
@dataclass(frozen=True)
class Settings:
    environment: str
    cors_origins: tuple[str, ...]
    database_path: Path


def get_settings() -> Settings:
    environment = os.getenv("APP_ENV", "localhost").lower()
    aliases = {"local": "localhost", "dev": "development", "prod": "production"}
    environment = aliases.get(environment, environment)
    if environment not in {"localhost", "development", "production"}:
        raise RuntimeError("APP_ENV localhost, development veya production olmalıdır")
    defaults = {"localhost": ("http://localhost:5173", "http://127.0.0.1:5173", "http://192.168.1.103:5173"),
                "development": ("https://dev.example.com",), "production": ("https://app.example.com",)}
    origins_default = defaults[environment]
    origins = tuple(x.strip() for x in os.getenv("CORS_ORIGINS", ",".join(origins_default)).split(",") if x.strip())
    database_default = ROOT.parent / "data" / f"gold_platform_{environment}.sqlite3"
    return Settings(environment, origins, Path(os.getenv("DATABASE_PATH", database_default)))


settings = get_settings()
