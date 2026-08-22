import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    environment: str
    model_dir: Path
    cors_origins: tuple[str, ...]
    auto_train: bool
    collection_interval_seconds: int
    retrain_minimum_rows: int
    retrain_every_new_rows: int
    keep_artifacts: int


def get_settings() -> Settings:
    environment = os.getenv("APP_ENV", "localhost").lower()
    aliases = {"local": "localhost", "dev": "development", "prod": "production"}
    environment = aliases.get(environment, environment)
    if environment not in {"localhost", "development", "production"}:
        raise RuntimeError("APP_ENV localhost, development veya production olmalıdır")
    # Servis SQLite kullanmıyor; yalnız CORS kaynakları ve otomatik eğitim varsayılanı ortama bağlı.
    defaults = {
        "localhost": (("http://127.0.0.1:8000", "http://localhost:8000"), True),
        "development": (("https://api-dev.example.com",), True),
        "production": (("https://app.example.com",), True),
    }
    origins_default, auto_default = defaults[environment]
    origins = tuple(x.strip() for x in os.getenv("CORS_ORIGINS", ",".join(origins_default)).split(",") if x.strip())
    return Settings(environment, Path(os.getenv("MODEL_DIR", ROOT / "models")), origins,
                    os.getenv("AUTO_TRAIN", str(auto_default)).lower() == "true",
                    int(os.getenv("COLLECTION_INTERVAL_SECONDS", "3600")), int(os.getenv("RETRAIN_MINIMUM_ROWS", "300")),
                    int(os.getenv("RETRAIN_EVERY_NEW_ROWS", "5")), int(os.getenv("KEEP_ARTIFACTS", "5")))


settings = get_settings()
