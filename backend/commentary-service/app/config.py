import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_secret_env() -> None:
    """Gizli anahtarlar (.env.secrets, git dışı): KEY=VALUE satırları; var olan ortam değişkenini ezmez."""
    path = Path(os.getenv("SECRET_ENV_PATH", ROOT / ".env.secrets"))
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    environment: str
    cors_origins: tuple[str, ...]
    database_path: Path
    data_dir: Path
    llm_config_path: Path
    calendar_path: Path
    auto_generate: bool
    check_interval_seconds: int
    trigger_move_pct: float
    min_interval_minutes: int
    max_age_minutes: int
    pipeline_mode: str
    llm_pause_seconds: int
    keep_versions: int
    admin_token: str = ""


def get_settings() -> Settings:
    load_secret_env()
    environment = os.getenv("APP_ENV", "localhost").lower()
    aliases = {"local": "localhost", "dev": "development", "prod": "production"}
    environment = aliases.get(environment, environment)
    if environment not in {"localhost", "development", "production"}:
        raise RuntimeError("APP_ENV localhost, development veya production olmalıdır")
    defaults = {
        "localhost": ("http://127.0.0.1:8000", "http://localhost:8000"),
        "development": ("https://api-dev.example.com",),
        "production": ("https://app.example.com",),
    }
    origins = tuple(x.strip() for x in os.getenv("CORS_ORIGINS", ",".join(defaults[environment])).split(",") if x.strip())
    database_default = ROOT.parent / "data" / f"gold_platform_{environment}.sqlite3"
    mode = os.getenv("PIPELINE_MODE", "full").lower()
    if mode not in {"full", "fast"}:
        raise RuntimeError("PIPELINE_MODE full veya fast olmalıdır")
    return Settings(
        environment, origins, Path(os.getenv("DATABASE_PATH", database_default)),
        Path(os.getenv("DATA_DIR", ROOT / "data")),
        Path(os.getenv("LLM_CONFIG_PATH", ROOT / "llm.toml")),
        Path(os.getenv("CALENDAR_PATH", ROOT / "calendar.toml")),
        os.getenv("AUTO_GENERATE", "true").lower() == "true",
        int(os.getenv("CHECK_INTERVAL_SECONDS", "300")),
        float(os.getenv("TRIGGER_MOVE_PCT", "0.5")),
        int(os.getenv("MIN_INTERVAL_MINUTES", "60")),
        int(os.getenv("MAX_AGE_MINUTES", "240")),
        mode,
        int(os.getenv("LLM_PAUSE_SECONDS", "4")),
        int(os.getenv("KEEP_VERSIONS", "20")),
        os.getenv("COMMENTARY_ADMIN_TOKEN", ""),
    )


settings = get_settings()
