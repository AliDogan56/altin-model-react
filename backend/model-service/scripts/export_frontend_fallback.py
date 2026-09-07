#!/usr/bin/env python3
"""XAU/USD CSV'sinden tarayıcı için nötr (model servisi yoksa) fallback üretir."""
import csv
import json
from pathlib import Path
from statistics import fmean, pstdev

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
source = ROOT / "data" / "xauusd_training_5y.csv"
target = PROJECT / "frontend" / "src" / "data" / "model.json"

rows = list(csv.DictReader(source.open(encoding="utf-8")))
features = [key for key in rows[0] if key not in {"date", "xauusd_close"} and not key.startswith("target_")]
horizons = [7, 14, 30]
x_columns = [[float(row[key]) for row in rows] for key in features]
history = [[row["date"], float(row["xauusd_close"])] for row in rows[-365:]]
closes = [value for _, value in history]
network = {
    "w1": [[0.0] for _ in features], "b1": [0.0],
    "w2": [[0.0]], "b2": [0.0],
    "w3": [[0.0 for _ in horizons]], "b3": [0.0 for _ in horizons],
}
artifact = {
    "source": "XAU/USD", "fallback": True, "features": features, "horizons": horizons,
    "xMean": [fmean(column) for column in x_columns],
    "xStd": [pstdev(column) or 1.0 for column in x_columns],
    "yMean": [0.0] * len(horizons), "yStd": [1.0] * len(horizons),
    "models": [network], "residual80": [0.035, 0.05, 0.075],
    "latest": {key: float(rows[-1][key]) for key in features},
    "latestPrice": closes[-1], "latestDate": rows[-1]["date"], "history": history,
    "resistance": {"r20": max(closes[-20:]), "r60": max(closes[-60:]), "momentumJumpPct": 0.0},
    "metrics": {}, "rows": len(rows), "testRows": 0,
}
target.write_text(json.dumps(artifact, separators=(",", ":")), encoding="utf-8")
print(target)
