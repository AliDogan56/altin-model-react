"""Yorum sürümleri: DATA_DIR/versions/<sürüm>/commentary.json + `current` sembolik bağı (atomik değişir).
API sözleşmesi İngilizce alanlardır; istem paketleri (latest/*.json) Türkçe anahtar taşır."""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import shutil

from ..config import settings
from ..market_constants import LEDGER_DIR, VERSIONS_DIR
from .narration_service import NARRATION_FILE, read_meta

DISCLAIMER = "Bu metin masanın o anki okumasıdır, yatırım tavsiyesi değildir."
RUNS_CSV = LEDGER_DIR / "commentary_runs.csv"


class CommentaryStore:
    def latest(self) -> dict | None:
        link = VERSIONS_DIR / "current"
        if not link.exists():
            return None
        item = json.loads((link.resolve() / "commentary.json").read_text())
        item["narration"] = read_meta(link.resolve())   # ses üretilmediyse None; arayüz cihaz sesine düşer
        try:
            item["age_seconds"] = int((dt.datetime.now(dt.UTC) - dt.datetime.fromisoformat(item["generated_at"])).total_seconds())
        except (KeyError, ValueError):
            item["age_seconds"] = None
        return item

    def save(self, anchor_output: dict, snapshot: dict, trigger_reason: str, durations: dict) -> dict:
        version = dt.datetime.now(dt.UTC).replace(microsecond=0).strftime("%Y%m%dT%H%M%SZ")
        version_dir = VERSIONS_DIR / version
        version_dir.mkdir(parents=True, exist_ok=True)
        live = snapshot.get("canli") or {}
        fix = snapshot.get("spot_lbma_pm") or {}
        usage = anchor_output.get("usage") or {}
        item = {
            "version": version,
            "as_of": anchor_output.get("as_of"),
            "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
            "run_mode": anchor_output.get("run_mode") or settings.pipeline_mode,
            "trigger": {"reason": trigger_reason, "price": live.get("fiyat")},
            "live": {"price": live["fiyat"], "source": live.get("kaynak", ""), "time_utc": snapshot.get("canli_zaman_utc"),
                     "change_vs_fix_pct": live.get("fikse_gore_pct"), "change_vs_fix_usd": live.get("fikse_gore_dolar"),
                     "change_vs_prev_close_pct": live.get("onceki_kapanisa_gore_pct"), "atr_multiple": live.get("hareket_atr_kati")} if live else None,
            "official_fix": {"date": fix["tarih"], "price": fix["fiyat"]} if fix else None,
            "title": anchor_output.get("title", ""),
            "headline": anchor_output.get("headline", ""),
            "summary": anchor_output.get("summary", ""),
            "sections": [{"id": s["id"], "title": s["title"], "text": s["text"]} for s in anchor_output.get("sections", [])],
            "usage": usage,
            "durations_seconds": durations,
            "disclaimer": DISCLAIMER,
        }
        (version_dir / "commentary.json").write_text(json.dumps(item, ensure_ascii=False, indent=2))
        link, temp = VERSIONS_DIR / "current", VERSIONS_DIR / f".current-{version}"
        os.symlink(version, temp)
        os.replace(temp, link)
        for old in sorted(p for p in VERSIONS_DIR.iterdir() if p.is_dir() and not p.is_symlink())[: -settings.keep_versions]:
            shutil.rmtree(old, ignore_errors=True)
        self._append_run(item)
        return item

    def runs(self) -> list[dict]:
        """Metin üretim defteri (bütçe sayacı buradan okur)."""
        if not RUNS_CSV.exists():
            return []
        with open(RUNS_CSV, newline="") as handle:
            return list(csv.DictReader(handle))

    def version_dir(self, version: str):
        return VERSIONS_DIR / version

    def latest_audio(self):
        """Son sürümün MP3 yolu; ses henüz yoksa None."""
        link = VERSIONS_DIR / "current"
        if not link.exists():
            return None
        path = link.resolve() / NARRATION_FILE
        return path if path.exists() else None

    @staticmethod
    def _append_run(item: dict) -> None:
        LEDGER_DIR.mkdir(parents=True, exist_ok=True)
        new = not RUNS_CSV.exists()
        usage = item.get("usage") or {}
        with open(RUNS_CSV, "a", newline="") as handle:
            writer = csv.writer(handle)
            if new:
                writer.writerow(["version", "run_mode", "trigger_reason", "price", "total_seconds", "input_tokens", "output_tokens", "models"])
            writer.writerow([item["version"], item["run_mode"], item["trigger"]["reason"], item["trigger"]["price"], item["durations_seconds"].get("total"),
                             sum(v.get("input_tokens", 0) for v in usage.values()), sum(v.get("output_tokens", 0) for v in usage.values()),
                             json.dumps({k: v.get("model") for k, v in usage.items()}, ensure_ascii=False)])


commentary_store = CommentaryStore()
