"""Teknik analiz doğrulama betiklerinin ortak parçaları — çevrimdışı, ağ yok.

Üç rapor betiği (`ta_compare_baseline`, `ta_backtest_levels`, `ta_momentum_report`)
aynı fixture'ları okur, aynı başlığı üretir ve `docs/technical/VALIDATION.md`
içinde **yalnız kendi bölümünü** değiştirir. Diğer bölümler ve elle yazılan
"Karar önerileri" bölümü dokunulmadan kalır; belge yoksa iskeleti kurulur.

Betikler `backend/market-service` içinden `.venv/bin/python scripts/<ad>.py`
ile çalışır; `app` paketi burada `sys.path`'e eklenir. Paket koduna ve
yapılandırmasına yazılmaz — bu modül yalnız okur ve raporlar.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

SCRIPTS = Path(__file__).resolve().parent
SERVICE = SCRIPTS.parent
REPO = SERVICE.parents[1]
FIXTURES = SERVICE / "tests" / "fixtures"
DOC = REPO / "docs" / "technical" / "VALIDATION.md"
DAILY_FIXTURE = FIXTURES / "xau_daily_20260906.json"

if str(SERVICE) not in sys.path:
    sys.path.insert(0, str(SERVICE))

from app.services.technical.candles import Candle, normalize_daily  # noqa: E402
from app.services.technical.config import CONFIG  # noqa: E402

# Belgedeki bölümler ve sırası. Betikler yalnız kendi anahtarını yazar;
# "karar" bölümü insana aittir, hiçbir betik ona dokunmaz.
SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("eski-yeni", "Eski → yeni", "ta_compare_baseline.py"),
    ("backtest", "Tarihsel destek/direnç tepkisi", "ta_backtest_levels.py"),
    ("momentum", "Günlük momentum kovaları", "ta_momentum_report.py"),
    ("karar", "Karar önerileri", ""),
)
TITLE = "# Teknik analiz paketi — çevrimdışı doğrulama\n"
INTRO = (
    "Bu belge `backend/market-service/scripts/ta_*.py` betiklerinin çıktısıdır. Betikler "
    "yalnız `tests/fixtures/` altındaki 2026-09-06 fixture'larını okur; ağa çıkmaz, sunucu "
    "açmaz, paket parametresine dokunmaz. Her bölüm kendi betiğiyle yeniden üretilir; "
    "\"Karar önerileri\" elle yazılır ve betikler onu korur. Sayılar ölçümdür, öneri "
    "değildir — bir eşiği dondurma kararı insanındır.\n"
)


# --- veri ---------------------------------------------------------------------

def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def daily_candles() -> list[Candle]:
    candles, quality = normalize_daily(load_fixture(DAILY_FIXTURE.name)["points"])
    if quality.status != "OK":
        raise RuntimeError(f"günlük fixture bozuk: {quality}")
    return candles


def dataset_sha256() -> str:
    return hashlib.sha256(DAILY_FIXTURE.read_bytes()).hexdigest()


# --- biçimleme ----------------------------------------------------------------

def num(value: Any, nd: int = 2, sign: bool = False) -> str:
    """Sayı → metin; None → em dash. Tablolar nokta ondalıklı kalır (makineyle
    karşılaştırılabilsin), düzyazı Türkçe."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "evet" if value else "hayır"
    if isinstance(value, int):
        return f"{value:+d}" if sign else str(value)
    if isinstance(value, float):
        return f"{value:+.{nd}f}" if sign else f"{value:.{nd}f}"
    return str(value)


def pct(value: Any, nd: int = 2, sign: bool = False) -> str:
    """Oran (0,012) → yüzde metni (%1.20)."""
    if value is None:
        return "—"
    return "%" + num(100.0 * float(value), nd, sign)


def md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    def cell(x: Any) -> str:
        text = x if isinstance(x, str) else num(x)
        return text.replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(cell(h) for h in headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        out.append("| " + " | ".join(cell(c) for c in row) + " |")
    return "\n".join(out) + "\n"


# --- belge --------------------------------------------------------------------

def _marker(key: str, edge: str) -> str:
    return f"<!-- ta:section:{key}:{edge} -->"


def header_block(extra: Sequence[tuple[str, str]] = ()) -> str:
    candles = daily_candles()
    rows = [
        ("Tarih", datetime.now(timezone.utc).date().isoformat()),
        ("Veri seti", f"`tests/fixtures/{DAILY_FIXTURE.name}` — {len(candles)} tamamlanmış günlük mum, "
                      f"{candles[0].date} → {candles[-1].date} (GC=F türevi)"),
        ("Veri seti sha256", f"`{dataset_sha256()}`"),
        ("config_hash", f"`{CONFIG.config_hash()}` (`TechnicalConfig.config_hash()`, ortam değişkeni ezmesi yok)"),
        ("Paket sürümü", f"`{CONFIG.version}`"),
        ("Python", sys.version.split()[0] + ", numpy yok"),
    ]
    rows.extend(extra)
    return "<!-- ta:header:start -->\n" + md_table(("Alan", "Değer"), rows) + "<!-- ta:header:end -->\n"


def _skeleton() -> str:
    parts = [TITLE, "\n", header_block(), "\n", INTRO, "\n"]
    for key, title, script in SECTIONS:
        parts.append(_marker(key, "start") + "\n")
        parts.append(f"## {title}\n\n")
        if script:
            parts.append(f"_(henüz üretilmedi: `scripts/{script}`)_\n")
        else:
            parts.append("_(insan yazar; betikler bu bölüme dokunmaz)_\n")
        parts.append(_marker(key, "end") + "\n\n")
    return "".join(parts)


def upsert_section(key: str, body: str) -> Path:
    """`key` bölümünün gövdesini (başlık dahil) değiştirir, başlığı tazeler.

    Bölüm gövdesi `## Başlık` satırıyla başlamalı. Belge yoksa iskelet kurulur.
    "karar" anahtarı bilerek reddedilir: o bölüm insana ait.
    """
    if key == "karar":
        raise ValueError("'karar' bölümü elle yazılır; betik yazamaz")
    if key not in {k for k, _, _ in SECTIONS}:
        raise ValueError(f"bilinmeyen bölüm: {key}")
    DOC.parent.mkdir(parents=True, exist_ok=True)
    text = DOC.read_text(encoding="utf-8") if DOC.exists() else _skeleton()
    start, end = _marker(key, "start"), _marker(key, "end")
    if start not in text or end not in text:
        raise RuntimeError(f"{DOC}: '{key}' bölüm işaretleri bulunamadı; belge elle bozulmuş")
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    replacement = start + "\n" + body.rstrip("\n") + "\n" + end
    text = pattern.sub(lambda _m: replacement, text, count=1)
    head = re.compile(r"<!-- ta:header:start -->.*?<!-- ta:header:end -->\n", re.S)
    text = head.sub(lambda _m: header_block(), text, count=1)
    DOC.write_text(text, encoding="utf-8")
    return DOC


def doc_size_kb() -> float:
    return DOC.stat().st_size / 1024.0 if DOC.exists() else 0.0
