#!/usr/bin/env python
"""Günlük momentum kovaları — skor, ileri getiriyle ilişkili mi ve ölçeği doğru mu?

`momentum_daily.score_series` yapısı gereği walk-forward (t'deki skor yalnız
t ve öncesini görür); burada seri bir kez hesaplanır, sonra her t için ileri
log getiri (1/5/10/20 mum) eşlenir. Kovalar: skor beşlikleri (eşit sayılı,
sıra ile) ve etiket aralıkları (0–20 … 80–100). Her kovada ortalama ileri
getiri, isabet (skor−50 işareti ile getirinin işareti aynı mı) ve sayı.
Spearman ρ elle (bağlı sıralar ortalama sıra). Skor histogramı, etiket
payları, skor sapması ve `z_scale` taraması **yalnız rapor** — yapılandırma
değişmez, `dataclasses.replace` ile yerel kopya kullanılır.

Örneklem uyarısı yazılıdır: ileri pencereler örtüşür; 20 günlük ufukta
örtüşmeyen gözlem ~60'tır. Ağ yok. Çıktı stdout + VALIDATION.md.
"""
from __future__ import annotations

import math
import statistics
import time
from dataclasses import replace
from typing import Sequence

import ta_report_common as common
from ta_report_common import md_table, num

from app.services.technical.config import CONFIG
from app.services.technical.momentum_daily import MIDPOINT, label_direction, score_series

HORIZONS = (1, 5, 10, 20)
LABEL_BINS = ((0, 20), (20, 40), (40, 60), (60, 80), (80, 101))
Z_SCAN = (2.0, 2.5, 3.0, 3.5, 4.0)
SD_TARGET = 15.0


def forward_log_returns(closes: Sequence[float], h: int) -> list[float | None]:
    return [math.log(closes[t + h] / closes[t]) if t + h < len(closes) else None for t in range(len(closes))]


def ranks(values: Sequence[float]) -> list[float]:
    """Bağlı değerlere ortalama sıra."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        mean_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = mean_rank
        i = j + 1
    return out


def spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) < 3 or len(set(x)) < 2 or len(set(y)) < 2:
        return None
    return statistics.correlation(ranks(x), ranks(y))


def bucket_stats(rows: Sequence[dict]) -> dict:
    out: dict = {"n": len(rows)}
    for h in HORIZONS:
        rets = [r[f"r{h}"] for r in rows]
        out[f"mean{h}"] = statistics.mean(rets) if rets else None
        decided = [(r["score"] - MIDPOINT, r[f"r{h}"]) for r in rows if r["score"] != MIDPOINT and r[f"r{h}"] != 0.0]
        out[f"hit{h}"] = (sum(1 for s, ret in decided if (s > 0) == (ret > 0)) / len(decided)) if decided else None
        out[f"nhit{h}"] = len(decided)
    return out


def _stat_rows(name: str, rows: Sequence[dict]) -> tuple:
    s = bucket_stats(rows)
    cells = [name, s["n"]]
    for h in HORIZONS:
        cells.append("—" if s[f"mean{h}"] is None else f"%{100 * s[f'mean{h}']:+.2f}")
    for h in HORIZONS:
        cells.append("—" if s[f"hit{h}"] is None else f"%{100 * s[f'hit{h}']:.0f}")
    return tuple(cells)


def main() -> None:
    t0 = time.perf_counter()
    candles = common.daily_candles()
    closes = [c.close for c in candles]
    params = CONFIG.momentum_daily
    scores = score_series(candles, params, CONFIG.indicators)
    fwd = {h: forward_log_returns(closes, h) for h in HORIZONS}

    rows = [{"t": t, "date": candles[t].date, "score": s, **{f"r{h}": fwd[h][t] for h in HORIZONS}}
            for t, s in enumerate(scores) if s is not None and all(fwd[h][t] is not None for h in HORIZONS)]
    all_scores = [s for s in scores if s is not None]
    n_scored = len(all_scores)

    # beşlikler: (skor, t) sırasıyla eşit sayılı; bağlar kova sınırında bölünür, aralık yazılır
    ordered = sorted(rows, key=lambda r: (r["score"], r["t"]))
    q = len(ordered) // 5
    quint_rows = []
    for k in range(5):
        chunk = ordered[k * q:(k + 1) * q] if k < 4 else ordered[4 * q:]
        name = f"Q{k + 1} [{chunk[0]['score']}–{chunk[-1]['score']}]"
        quint_rows.append(_stat_rows(name, chunk))
    label_rows = []
    for lo, hi in LABEL_BINS:
        chunk = [r for r in rows if lo <= r["score"] < hi]
        label_rows.append(_stat_rows(f"[{lo}, {min(hi, 100)}{']' if hi > 100 else ')'}", chunk))
    label_rows.append(_stat_rows("Tümü", rows))

    # Spearman: tam örneklem + örtüşmeyen alt örneklem (her h. gözlem)
    rho_rows = []
    for h in HORIZONS:
        xs = [r["score"] for r in rows]
        ys = [r[f"r{h}"] for r in rows]
        rho = spearman(xs, ys)
        sub = rows[::h]
        rho_sub = spearman([r["score"] for r in sub], [r[f"r{h}"] for r in sub])
        t_stat = None if rho is None or abs(rho) >= 1 else rho * math.sqrt((len(xs) - 2) / (1 - rho * rho))
        rho_rows.append((f"{h} mum", len(xs), num(rho, 3, sign=True), num(t_stat, 2, sign=True),
                         len(sub), num(rho_sub, 3, sign=True)))

    # histogram, etiket payları, sapma
    hist = [0] * 10
    for s in all_scores:
        hist[min(9, s // 10)] += 1
    hist_rows = [(f"[{10 * i}, {10 * i + 10}{')' if i < 9 else ']'}", n, f"%{100 * n / n_scored:.1f}",
                  "█" * int(round(40 * n / max(hist)))) for i, n in enumerate(hist)]
    shares = {d: sum(1 for s in all_scores if label_direction(s, params) == d) / n_scored for d in ("UP", "NEUTRAL", "DOWN")}
    sd = statistics.stdev(all_scores)
    mean = statistics.mean(all_scores)

    # z_scale taraması (yalnız rapor)
    scan_rows = []
    scan_sd: list[tuple[float, float]] = []
    for z in Z_SCAN:
        local = replace(params, z_scale=z)
        s_z = [s for s in score_series(candles, local, CONFIG.indicators) if s is not None]
        sd_z = statistics.stdev(s_z)
        scan_sd.append((z, sd_z))
        sh = {d: sum(1 for s in s_z if label_direction(s, params) == d) / len(s_z) for d in ("UP", "NEUTRAL", "DOWN")}
        scan_rows.append((f"{z:.1f}", f"{sd_z:.2f}", f"{statistics.mean(s_z):.1f}",
                          f"%{100 * sh['UP']:.0f} / %{100 * sh['NEUTRAL']:.0f} / %{100 * sh['DOWN']:.0f}",
                          "✓" if z == params.z_scale else ""))
    # hedef sapma için doğrusal ara değer (rapor amaçlı; kesin değer taramada okunmalı)
    z_star = None
    for (z1, s1), (z2, s2) in zip(scan_sd, scan_sd[1:]):
        if (s1 - SD_TARGET) * (s2 - SD_TARGET) <= 0 and s1 != s2:
            z_star = z1 + (SD_TARGET - s1) * (z2 - z1) / (s2 - s1)
            break
    closest = min(scan_sd, key=lambda p: abs(p[1] - SD_TARGET))
    elapsed = time.perf_counter() - t0

    head = ("Kova", "n") + tuple(f"ort. {h}m" for h in HORIZONS) + tuple(f"isabet {h}m" for h in HORIZONS)
    parts = [
        "## Günlük momentum kovaları\n",
        f"`score_series` {len(candles)} mumda {n_scored} skor üretti (ısınma {len(candles) - n_scored} mum); ileri getiri "
        f"için 20 mum kuyruk düşünce **{len(rows)} gözlem** ({rows[0]['date']} → {rows[-1]['date']}). Ortalama ileri "
        f"getiri log getiri (%), isabet = (skor − 50) işareti ile ileri getirinin işareti aynı (skor = 50 ve sıfır "
        f"getiri hariç). Parametreler: z_scale {params.z_scale}, UP ≥ {params.up}, DOWN ≤ {params.down}.\n\n",
        "### Beşlikler (eşit sayılı, skor sırasıyla)\n\n", md_table(head, quint_rows),
        "\n### Etiket aralıkları\n\n", md_table(head, label_rows),
        "\n### Spearman ρ (skor ↔ ileri log getiri)\n\n",
        md_table(("Ufuk", "n (örtüşen)", "ρ", "t ≈ ρ√((n−2)/(1−ρ²))", "n (örtüşmeyen)", "ρ örtüşmeyen"), rho_rows),
        "\n`t` sütunu bağımsız gözlem varsayar; örtüşen pencerelerde **abartılıdır**, yalnız ölçek için yazıldı. "
        "Örtüşmeyen sütun her h. gözlemi alır (tek bir faz; başka faz başka sayı verir).\n\n",
        "### Skor dağılımı\n\n", md_table(("Aralık", "n", "Pay", ""), hist_rows),
        f"\nOrtalama {mean:.1f}, ortanca {statistics.median(all_scores):.0f}, **sapma {sd:.2f}** (tasarım hedefi ≈ {SD_TARGET:.0f}). "
        f"Etiket payları: UP %{100 * shares['UP']:.1f} · NEUTRAL %{100 * shares['NEUTRAL']:.1f} · DOWN %{100 * shares['DOWN']:.1f}.\n\n",
        "### `z_scale` taraması (yalnız rapor; yapılandırma değişmedi)\n\n",
        md_table(("z_scale", "Sapma", "Ortalama", "UP / NEUTRAL / DOWN", "Mevcut"), scan_rows),
        f"\nSapma {SD_TARGET:.0f}'e en yakın taranan değer z_scale = **{closest[0]:.1f}** (sapma {closest[1]:.2f})"
        + (f"; doğrusal ara değerle ≈ **{z_star:.2f}**" if z_star is not None else "; taranan aralıkta hedef kesilmedi")
        + ". Skor = 50 + 50·tanh(z / z_scale) olduğu için z_scale büyüdükçe skor 50'ye sıkışır ve UP/DOWN payı düşer; "
        "eşikler (60/40) sabit kalırsa sapmayı 15'e indirmek etiketlerin seyrekleşmesi demektir — ikisi birlikte karar verilmeli.\n\n",
        "### Örneklem uyarısı\n\n",
        f"{len(rows)} gözlem **örtüşen** pencerelerden geliyor: 20 mumluk ufukta bağımsız gözlem sayısı ~{len(rows) // 20}, "
        "5 mumlukta ~"
        f"{len(rows) // 5}. Repo dersi: 33 örtüşmeyen 30 günlük pencere gürültüydü. Kovalar arasındaki birkaç puanlık "
        "isabet farkı ya da 0.1'in altındaki ρ, bu örneklemde sıfırdan ayırt edilemez; ancak işaretin ufuklar boyunca "
        "tutarlı olması ve büyük kova farkları bilgi taşır. Ayrıca seri 2021–2026 tek bir rejimi (uzun yükseliş) "
        "kapsıyor — UP payının yüksekliği kısmen bunun eseri.\n"
        f"\n_Betik süresi {elapsed:.2f} s._\n",
    ]
    body = "".join(parts)
    print(body)
    path = common.upsert_section("momentum", body)
    print(f"\n→ {path} ({common.doc_size_kb():.1f} KB), elapsed {elapsed:.2f} s")


if __name__ == "__main__":
    main()
