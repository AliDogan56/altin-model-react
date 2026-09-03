import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ServiceRoute:
    name: str
    base_url: str
    prefixes: tuple[str, ...]


@dataclass(frozen=True)
class Settings:
    environment: str
    cors_origins: tuple[str, ...]
    routes: tuple[ServiceRoute, ...]
    default_service: ServiceRoute
    database_path: Path
    # Üst servise bekleme süresi (sn). Eskiden 300 idi: takılan bir üst servis
    # gateway işçisini ve istemci bağlantısını beş dakika tutuyordu. Ölçülen en
    # uzun meşru yol market-service'in birincil + yedek fiyat kaynağı (30 + 30 sn);
    # 90 onu kapsar. Elle yeniden eğitim (/v1/training) veri setini de tazelediği
    # için ayrı, uzun bir sınır alır.
    upstream_timeout: float
    slow_timeout: float
    slow_prefixes: tuple[str, ...]


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(value.strip() for value in os.getenv(name, default).split(",") if value.strip())


def get_settings() -> Settings:
    environment = os.getenv("APP_ENV", "localhost")
    model = ServiceRoute("model-service", os.getenv("MODEL_SERVICE_URL", "http://127.0.0.1:8002").rstrip("/"),
                         _csv("MODEL_SERVICE_PREFIXES", "/v1/predict,/v1/snapshots,/v1/learning,/v1/training"))
    backend = ServiceRoute("market-service", os.getenv("MARKET_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/"),
                           _csv("MARKET_SERVICE_PREFIXES", "/v1/market"))
    database_default = ROOT.parent / "data" / f"gold_platform_{environment}.sqlite3"
    return Settings(environment, _csv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://192.168.1.103:5173"),
                    (model, backend), backend, Path(os.getenv("DATABASE_PATH", database_default)),
                    float(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "90")),
                    float(os.getenv("UPSTREAM_SLOW_TIMEOUT_SECONDS", "300")),
                    _csv("UPSTREAM_SLOW_PREFIXES", "/v1/training"))


settings = get_settings()
