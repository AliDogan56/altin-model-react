import sqlite3
from datetime import datetime, timezone

from .config import settings


def initialize() -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.database_path, timeout=30) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=30000")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS service_registry (
          service_name TEXT PRIMARY KEY, environment TEXT NOT NULL, last_seen_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS market_cache_metadata (
          cache_key TEXT PRIMARY KEY, source TEXT NOT NULL, refreshed_at TEXT NOT NULL
        );
        """)
        db.execute("INSERT INTO service_registry(service_name,environment,last_seen_at) VALUES(?,?,?) ON CONFLICT(service_name) DO UPDATE SET environment=excluded.environment,last_seen_at=excluded.last_seen_at",
                   ("market-service", settings.environment, datetime.now(timezone.utc).isoformat()))
