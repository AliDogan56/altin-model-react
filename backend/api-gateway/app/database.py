import sqlite3
from datetime import datetime, timezone

from .config import settings


def connect() -> sqlite3.Connection:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.database_path, timeout=30)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=30000")
    return connection


def initialize() -> None:
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS service_registry (
          service_name TEXT PRIMARY KEY, environment TEXT NOT NULL, last_seen_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gateway_request_logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT, requested_at TEXT NOT NULL, method TEXT NOT NULL,
          path TEXT NOT NULL, target_service TEXT NOT NULL, status_code INTEGER NOT NULL, duration_ms REAL NOT NULL
        );
        """)
        db.execute("INSERT INTO service_registry(service_name,environment,last_seen_at) VALUES(?,?,?) ON CONFLICT(service_name) DO UPDATE SET environment=excluded.environment,last_seen_at=excluded.last_seen_at",
                   ("api-gateway", settings.environment, datetime.now(timezone.utc).isoformat()))


def log_request(method: str, path: str, target: str, status_code: int, duration_ms: float) -> None:
    with connect() as db:
        db.execute("INSERT INTO gateway_request_logs(requested_at,method,path,target_service,status_code,duration_ms) VALUES(?,?,?,?,?,?)",
                   (datetime.now(timezone.utc).isoformat(), method, path, target, status_code, duration_ms))
