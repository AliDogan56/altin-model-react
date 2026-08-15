import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from .config import settings


@contextmanager
def connect():
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(settings.database_path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    finally:
        db.close()


def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS service_registry (
          service_name TEXT PRIMARY KEY, environment TEXT NOT NULL, last_seen_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS observations (
          trade_date TEXT PRIMARY KEY,
          observed_at TEXT NOT NULL,
          price REAL NOT NULL,
          display_price REAL NOT NULL,
          basis_usd REAL NOT NULL,
          source TEXT NOT NULL,
          display_source TEXT NOT NULL,
          features_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS prediction_runs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          base_date TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL,
          base_price REAL NOT NULL,
          model_version TEXT NOT NULL,
          features_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS prediction_targets (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          run_id INTEGER NOT NULL REFERENCES prediction_runs(id) ON DELETE CASCADE,
          horizon_days INTEGER NOT NULL,
          target_date TEXT NOT NULL,
          predicted_return REAL NOT NULL,
          predicted_price REAL NOT NULL,
          lower_price REAL NOT NULL,
          upper_price REAL NOT NULL,
          actual_date TEXT,
          actual_price REAL,
          actual_return REAL,
          error REAL,
          abs_error REAL,
          direction_correct INTEGER,
          band_covered INTEGER,
          settled_at TEXT,
          UNIQUE(run_id, horizon_days)
        );
        CREATE INDEX IF NOT EXISTS idx_targets_due ON prediction_targets(target_date, actual_price);
        CREATE TABLE IF NOT EXISTS model_versions (
          version TEXT PRIMARY KEY,
          created_at TEXT NOT NULL,
          artifact_path TEXT NOT NULL,
          metrics_json TEXT NOT NULL,
          training_rows INTEGER NOT NULL,
          active INTEGER NOT NULL DEFAULT 0
        );
        """)
        db.execute("INSERT INTO service_registry(service_name,environment,last_seen_at) VALUES(?,?,?) ON CONFLICT(service_name) DO UPDATE SET environment=excluded.environment,last_seen_at=excluded.last_seen_at",
                   ("model-service", settings.environment, datetime.now(timezone.utc).isoformat()))


def save_snapshot(trade_date: date, observed_at: datetime, model_price: float, display_price: float, source: str, display_source: str, features: dict, forecast: dict):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        db.execute(
            """INSERT INTO observations(trade_date,observed_at,price,display_price,basis_usd,source,display_source,features_json)
               VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(trade_date) DO UPDATE SET
               observed_at=excluded.observed_at,price=excluded.price,display_price=excluded.display_price,basis_usd=excluded.basis_usd,
               source=excluded.source,display_source=excluded.display_source,features_json=excluded.features_json""",
            (trade_date.isoformat(), observed_at.isoformat(), model_price, display_price, display_price-model_price, source, display_source, json.dumps(features)),
        )
        row = db.execute("SELECT id FROM prediction_runs WHERE base_date=?", (trade_date.isoformat(),)).fetchone()
        created = row is None
        if created:
            cur = db.execute(
                "INSERT INTO prediction_runs(base_date,created_at,base_price,model_version,features_json) VALUES(?,?,?,?,?)",
                (trade_date.isoformat(), now, model_price, forecast["version"], json.dumps(features)),
            )
            run_id = cur.lastrowid
            for index, horizon in enumerate(forecast["horizons"]):
                predicted_return = forecast["mean"][index]
                error = forecast["error"][index]
                db.execute(
                    """INSERT INTO prediction_targets(run_id,horizon_days,target_date,predicted_return,predicted_price,lower_price,upper_price)
                       VALUES(?,?,?,?,?,?,?)""",
                    (run_id, horizon, (trade_date + timedelta(days=horizon)).isoformat(), predicted_return,
                     model_price * (1 + predicted_return), model_price * (1 + predicted_return - error), model_price * (1 + predicted_return + error)),
                )
        settle_due(db, trade_date, model_price, now)
    return created


def settle_due(db: sqlite3.Connection, actual_date: date, actual_price: float, settled_at: str):
    rows = db.execute(
        """SELECT t.id,t.predicted_return,t.lower_price,t.upper_price,r.base_price
           FROM prediction_targets t JOIN prediction_runs r ON r.id=t.run_id
           WHERE t.actual_price IS NULL AND t.target_date<=?""", (actual_date.isoformat(),)
    ).fetchall()
    for row in rows:
        actual_return = actual_price / row["base_price"] - 1
        error = actual_return - row["predicted_return"]
        db.execute(
            """UPDATE prediction_targets SET actual_date=?,actual_price=?,actual_return=?,error=?,abs_error=?,
               direction_correct=?,band_covered=?,settled_at=? WHERE id=?""",
            (actual_date.isoformat(), actual_price, actual_return, error, abs(error),
             int((actual_return >= 0) == (row["predicted_return"] >= 0)),
             int(row["lower_price"] <= actual_price <= row["upper_price"]), settled_at, row["id"]),
        )


def metrics():
    with connect() as db:
        rows = db.execute("""SELECT horizon_days,COUNT(*) samples,AVG(abs_error) mae,
          SQRT(AVG(error*error)) rmse,AVG(direction_correct) direction_accuracy,AVG(band_covered) band_coverage,
          AVG(error) mean_bias FROM prediction_targets WHERE actual_price IS NOT NULL GROUP BY horizon_days ORDER BY horizon_days""").fetchall()
        pending = db.execute("SELECT COUNT(*) n FROM prediction_targets WHERE actual_price IS NULL").fetchone()["n"]
        runs = db.execute("SELECT COUNT(*) n FROM prediction_runs").fetchone()["n"]
    return {"prediction_days": runs, "pending_targets": pending, "horizons": [dict(row) for row in rows]}


def training_rows(feature_names: list[str], horizons: list[int]):
    with connect() as db:
        observations = [dict(row) for row in db.execute("SELECT * FROM observations ORDER BY trade_date").fetchall()]
    by_date = {row["trade_date"]: row for row in observations}
    x, y = [], []
    for row in observations:
        base_date = date.fromisoformat(row["trade_date"])
        future = [by_date.get((base_date + timedelta(days=h)).isoformat()) for h in horizons]
        if any(item is None for item in future):
            continue
        features = json.loads(row["features_json"])
        if any(name not in features for name in feature_names):
            continue
        x.append([float(features[name]) for name in feature_names])
        y.append([item["price"] / row["price"] - 1 for item in future])
    return x, y
