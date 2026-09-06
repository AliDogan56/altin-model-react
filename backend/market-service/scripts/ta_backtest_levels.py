#!/usr/bin/env python
"""Tarihsel destek/direnç tepkisi — bölge gücü, tutmayı öngörüyor mu?

İleri bakışsız yürüyen pencere: her `t` için yalnız `candles[:t]` görülür
(bölgeler, ATR, pivotlar), sonra **sonraki 10 mum** gözlenir. Bir bölge
"test edildi" sayılır ⇔ fiyat [low, high] bandına 0.25·ATR_t içine gelir;
test edilen bölgede temastan sonraki 5 mumun kapanışlarına göre:

* **BREAK**: uzak kenarın ötesinde ≥ 0.5·ATR_t bir kapanış
* **HOLD**: yaklaşılan yandan ≥ 1·ATR_t uzaklaşan bir kapanış VE uzak kenarın
  ötesinde hiç kapanış yok
* **NONE**: ikisi de değil (bölgede oyalanma)

Yaklaşma yanı bölgenin `t` anındaki türüdür (SUPPORT yukarıdan, RESISTANCE
aşağıdan). `t` anında zaten marj içinde olan (`testing`) bölgeler yaklaşma
yanı belirsiz olduğu için dışarıda tutulur; onaysız (yalnız DEVELOPING üyeli)
bölgeler hiç hedef olamayacağı için ayrıca sayılır.

Tutma oranı = HOLD / (HOLD + BREAK). Karşılaştırma tabanı iki tane: havuz
(bütün test edilen bölgeler) ve **plasebo** — aynı kuralla test edilen rastgele
fiyat seviyeleri (bölge değil, fiyatın ±6 ATR'sinde tohumlu rastgele nokta,
asgari bölge genişliği). En zayıf dilimin plaseboyu geçmesi "bölge olmak bile
bir şey söylüyor" demektir; havuz ortalamasını geçmesi ise dilimler ayrışmış
olsa imkânsızdır (havuz onların ağırlıklı ortalaması) — iki taban da yazılır.

Ağ yok, paket parametresi değiştirilmez; ızgara `dataclasses.replace` ile
**yerel** kopyalar üzerinde koşar. Çıktı stdout + VALIDATION.md.
"""
from __future__ import annotations

import random
import statistics
import time
from dataclasses import replace
from datetime import timedelta
from typing import Sequence

import ta_report_common as common
from ta_report_common import md_table, num

from app.services.technical.assemble import _structural_pivots
from app.services.technical.candles import Candle
from app.services.technical.config import CONFIG
from app.services.technical.levels import (
    KIND_SUPPORT, LABEL_MODERATE, LABEL_STRONG, LABEL_WEAK, LevelParams, Levels, analyze_levels,
)
from app.services.technical.pivots import compute_all

START, STEP, LOOKAHEAD, REACTION = 300, 5, 10, 5
TOUCH_ATR, HOLD_ATR, BREAK_ATR = 0.25, 1.0, 0.5
PLACEBO_PER_DATE, PLACEBO_SPAN_ATR = 5, 6.0
SEED = 20260906
HOLD, BREAK, NONE = "HOLD", "BREAK", "NONE"
LABELS = (LABEL_STRONG, LABEL_MODERATE, LABEL_WEAK)
GRID_HALF_LIFE = (30.0, 60.0, 90.0, 120.0)
GRID_WING = (2, 3, 5)


# --- yürüyen pencere --------------------------------------------------------------

class PivotCache:
    """Pivotlar `LevelParams`'a bağlı değil; `t` başına bir kez hesaplanır."""

    def __init__(self, candles: Sequence[Candle]):
        self.candles = candles
        self._cache: dict[int, list[tuple[str, float]]] = {}

    def at(self, t: int) -> list[tuple[str, float]]:
        if t not in self._cache:
            bars = self.candles[:t]
            today = bars[-1].date + timedelta(days=1)   # assemble: `daily = date < today`
            self._cache[t] = _structural_pivots(compute_all(bars, today, CONFIG.pivots, CONFIG.completion))
        return self._cache[t]


def zones_at(candles: Sequence[Candle], t: int, params: LevelParams, pivots: PivotCache | None = None) -> Levels:
    """`t` anındaki bölge haritası: yalnız `candles[:t]` görülür."""
    bars = candles[:t]
    pivot_levels = pivots.at(t) if pivots else _structural_pivots(
        compute_all(bars, bars[-1].date + timedelta(days=1), CONFIG.pivots, CONFIG.completion))
    return analyze_levels(bars, bars[-1].close, pivot_levels=pivot_levels, params=params,
                          indicator_params=CONFIG.indicators)


def react(candles: Sequence[Candle], t: int, low: float, high: float, support: bool, atr: float) -> str | None:
    """None: 10 mumda test yok ya da tepki penceresi seride tamamlanmıyor."""
    margin = TOUCH_ATR * atr
    touch = next((k for k, bar in enumerate(candles[t:t + LOOKAHEAD])
                  if bar.low <= high + margin and bar.high >= low - margin), None)
    if touch is None:
        return None
    after = candles[t + touch + 1:t + touch + 1 + REACTION]
    if len(after) < REACTION:
        return None
    closes = [bar.close for bar in after]
    if support:
        broke = any(c <= low - BREAK_ATR * atr for c in closes)
        held = all(c >= low for c in closes) and any(c >= high + HOLD_ATR * atr for c in closes)
    else:
        broke = any(c >= high + BREAK_ATR * atr for c in closes)
        held = all(c <= high for c in closes) and any(c <= low - HOLD_ATR * atr for c in closes)
    return BREAK if broke else HOLD if held else NONE


def run(candles: Sequence[Candle], params: LevelParams, pivots: PivotCache, step: int = STEP
        ) -> tuple[list[dict], dict[str, int]]:
    """Her (tarih, bölge) için kayıt; sayaçlar: bölge / dışlanan / test edilmeyen."""
    records: list[dict] = []
    counts = {"dates": 0, "zones": 0, "testing_excluded": 0, "unconfirmed_excluded": 0, "untested": 0,
              "incomplete": 0}
    n = len(candles)
    for t in range(START, n - LOOKAHEAD + 1, step):
        lv = zones_at(candles, t, params, pivots)
        if lv.status != "OK":
            continue
        counts["dates"] += 1
        for z in lv.zones:
            counts["zones"] += 1
            if not z.confirmed:
                counts["unconfirmed_excluded"] += 1
                continue
            if z.testing:
                counts["testing_excluded"] += 1
                continue
            outcome = react(candles, t, z.low, z.high, z.kind == KIND_SUPPORT, lv.atr)
            if outcome is None:
                touch = any(bar.low <= z.high + TOUCH_ATR * lv.atr and bar.high >= z.low - TOUCH_ATR * lv.atr
                            for bar in candles[t:t + LOOKAHEAD])
                counts["incomplete" if touch else "untested"] += 1
                continue
            records.append({"t": t, "date": candles[t - 1].date, "id": z.id, "strength": z.strength,
                            "label": z.label, "kind": z.kind, "touches": z.touches, "outcome": outcome,
                            "distance_atr": abs(z.distance_atr), "sources": len(z.source_types)})
    return records, counts


def placebo(candles: Sequence[Candle], pivots: PivotCache, step: int = STEP) -> list[dict]:
    """Rastgele seviyeler, aynı test/tepki kuralı. ATR yürüyen pencerenin kendisinden.
    Kayıt `{"kind", "outcome"}`: yan ayrımı şart, çünkü yükseliş rejiminde destek
    ile direncin tutma oranı çok farklı ve bölge kümesinin yan karışımı rastgele
    seviyelerinkinden farklı olabilir."""
    rng = random.Random(SEED)
    outcomes: list[dict] = []
    n = len(candles)
    for t in range(START, n - LOOKAHEAD + 1, step):
        lv = zones_at(candles, t, CONFIG.levels, pivots)
        if lv.status != "OK":
            continue
        ref, atr = candles[t - 1].close, lv.atr
        half = CONFIG.levels.zone_min_half_width_atr * atr
        margin = TOUCH_ATR * atr
        made = 0
        while made < PLACEBO_PER_DATE:
            level = ref + rng.uniform(-PLACEBO_SPAN_ATR, PLACEBO_SPAN_ATR) * atr
            low, high = level - half, level + half
            if low - margin <= ref <= high + margin:      # fiyatın üstünde durduğu seviye: test edilen sayılır, atla
                continue
            made += 1
            outcome = react(candles, t, low, high, level < ref, atr)
            if outcome is not None:
                outcomes.append({"kind": KIND_SUPPORT if level < ref else "RESISTANCE", "outcome": outcome})
    return outcomes


# --- özetler ----------------------------------------------------------------------

def rate(outcomes: Sequence[str]) -> tuple[int, int, int, float | None]:
    h = sum(1 for o in outcomes if o == HOLD)
    b = sum(1 for o in outcomes if o == BREAK)
    o_ = sum(1 for o in outcomes if o == NONE)
    return h, b, o_, (h / (h + b) if h + b else None)


def terciles(records: Sequence[dict]) -> list[tuple[str, list[dict]]]:
    strengths = sorted(r["strength"] for r in records)
    if not strengths:
        return []
    lo, hi = strengths[len(strengths) // 3], strengths[2 * len(strengths) // 3]
    groups = {"T1 (zayıf)": [], "T2": [], "T3 (güçlü)": []}
    for r in records:
        key = "T1 (zayıf)" if r["strength"] < lo else "T2" if r["strength"] < hi else "T3 (güçlü)"
        groups[key].append(r)
    out = []
    for key, items in groups.items():
        if items:
            span = f"{min(i['strength'] for i in items)}–{max(i['strength'] for i in items)}"
            out.append((f"{key} [{span}]", items))
    return out


def by_label(records: Sequence[dict]) -> dict[str, list[dict]]:
    return {label: [r for r in records if r["label"] == label] for label in LABELS}


def _rate_row(name: str, items: Sequence[dict | str]) -> tuple:
    outcomes = [i["outcome"] if isinstance(i, dict) else i for i in items]
    h, b, o_, r = rate(outcomes)
    share_none = o_ / len(outcomes) if outcomes else None
    return (name, len(outcomes), h, b, o_, "—" if r is None else f"%{100 * r:.1f}",
            "—" if share_none is None else f"%{100 * share_none:.0f}")


def _pct(value: float | None) -> str:
    return "—" if value is None else f"%{100 * value:.1f}"


def monotone(values: Sequence[float | None]) -> bool:
    return all(v is not None for v in values) and all(a > b for a, b in zip(values, values[1:]))


def lookahead_proof(candles: Sequence[Candle], params: LevelParams) -> tuple[int, int]:
    rng = random.Random(SEED + 1)
    ok = 0
    picks = sorted(rng.sample(range(START, len(candles) - LOOKAHEAD), 10))
    for t in picks:
        perturbed = list(candles[:t])
        for bar in candles[t:]:
            f = rng.uniform(0.8, 1.2)
            perturbed.append(replace(bar, high=bar.high * f * 1.01, low=bar.low * f * 0.99, close=bar.close * f))
        tail = perturbed[t:]         # sıra da bozulsun; yalnız `[:t]` dilimi görülmeli
        rng.shuffle(tail)
        perturbed[t:] = tail
        assert perturbed[t:] != list(candles[t:]) and perturbed[:t] == list(candles[:t])
        a, b = zones_at(candles, t, params), zones_at(perturbed, t, params)
        ok += a == b
    return ok, len(picks)


# --- rapor ---------------------------------------------------------------------------

def main() -> None:
    t0 = time.perf_counter()
    candles = common.daily_candles()
    pivots = PivotCache(candles)
    base = CONFIG.levels

    records, counts = run(candles, base, pivots)
    placebo_outcomes = placebo(candles, pivots)
    t_base = time.perf_counter() - t0

    pooled = rate([r["outcome"] for r in records])
    plac = rate([p["outcome"] for p in placebo_outcomes])
    plac_side = {kind: rate([p["outcome"] for p in placebo_outcomes if p["kind"] == kind])
                 for kind in ("SUPPORT", "RESISTANCE")}
    zone_side = {kind: rate([r["outcome"] for r in records if r["kind"] == kind]) for kind in ("SUPPORT", "RESISTANCE")}
    label_groups = by_label(records)
    label_rates = [rate([r["outcome"] for r in label_groups[l]])[3] for l in LABELS]
    terc = terciles(records)
    terc_rates = [rate([r["outcome"] for r in items])[3] for _, items in terc]

    # yoğun örneklem: her mum (yalnız temel yapılandırma), örtüşme daha fazla ama sayı daha yüksek
    dense_records, dense_counts = run(candles, base, pivots, step=1)
    dense_label = by_label(dense_records)
    dense_terc = terciles(dense_records)

    # ızgara
    grid_rows = []
    grid_t0 = time.perf_counter()
    for hl in GRID_HALF_LIFE:
        for wing in GRID_WING:
            p = replace(base, recency_half_life_days=hl, swing_wing=wing)
            recs, _ = run(candles, p, pivots)
            lab = by_label(recs)
            lr = [rate([r["outcome"] for r in lab[l]])[3] for l in LABELS]
            tr = [rate([r["outcome"] for r in items])[3] for _, items in terciles(recs)]
            ns = [len(lab[l]) for l in LABELS]
            grid_rows.append((f"{hl:.0f}", wing, len(recs),
                              " / ".join("—" if r is None else f"%{100 * r:.1f}" for r in lr),
                              " / ".join(str(n) for n in ns),
                              " / ".join("—" if r is None else f"%{100 * r:.1f}" for r in reversed(tr)),
                              "evet" if monotone(lr) else "hayır", "evet" if monotone(list(reversed(tr))) else "hayır",
                              "✓" if (hl, wing) == (base.recency_half_life_days, base.swing_wing) else ""))
    t_grid = time.perf_counter() - grid_t0
    proof_ok, proof_n = lookahead_proof(candles, base)
    elapsed = time.perf_counter() - t0

    # kapı
    label_mono = monotone(label_rates)
    terc_mono = monotone(list(reversed(terc_rates)))     # T3 > T2 > T1
    lowest = terc_rates[0] if terc_rates else None
    gate_pool = lowest is not None and pooled[3] is not None and lowest >= pooled[3]
    gate_plac = lowest is not None and plac[3] is not None and lowest >= plac[3]
    gate = label_mono and terc_mono and gate_plac
    strengths = [r["strength"] for r in records]
    holds = [1.0 if r["outcome"] == HOLD else 0.0 for r in records if r["outcome"] != NONE]
    str_decided = [r["strength"] for r in records if r["outcome"] != NONE]
    corr = statistics.correlation(str_decided, holds) if len(set(holds)) > 1 and len(set(str_decided)) > 1 else None

    rows_main = [_rate_row("Havuz (bütün test edilen bölgeler)", records),
                 _rate_row("Plasebo (rastgele seviye, aynı kural)", placebo_outcomes)]
    rows_main += [_rate_row(name, items) for name, items in terc]
    rows_main += [_rate_row(f"Etiket {label}", label_groups[label]) for label in LABELS]
    rows_dense = [_rate_row("Havuz, her mum", dense_records)]
    rows_dense += [_rate_row(name, items) for name, items in dense_terc]
    rows_dense += [_rate_row(f"Etiket {label}", dense_label[label]) for label in LABELS]

    # tür ve uzaklık kesitleri (yorum için)
    kind_rows = []
    for kind in ("SUPPORT", "RESISTANCE"):
        kind_rows.append(_rate_row(f"Bölge {kind}", [r for r in records if r["kind"] == kind]))
        kind_rows.append(_rate_row(f"Plasebo {kind}", [p for p in placebo_outcomes if p["kind"] == kind]))
    for kind in ("SUPPORT", "RESISTANCE"):
        side_records = [r for r in records if r["kind"] == kind]
        for name, items in terciles(side_records):
            kind_rows.append(_rate_row(f"{kind} · {name}", items))
    near = [r for r in records if r["distance_atr"] <= 2.0]
    far = [r for r in records if r["distance_atr"] > 2.0]
    kind_rows.append(_rate_row("Uzaklık ≤ 2 ATR (t anında)", near))
    kind_rows.append(_rate_row("Uzaklık > 2 ATR", far))
    touched = [r for r in records if r["touches"] >= 3]
    untouched = [r for r in records if r["touches"] <= 1]
    kind_rows.append(_rate_row("Geçmiş temas ≥ 3", touched))
    kind_rows.append(_rate_row("Geçmiş temas ≤ 1", untouched))

    parts = [
        "## Tarihsel destek/direnç tepkisi\n",
        f"Yürüyen pencere: `t` = {START} … {len(candles) - LOOKAHEAD} her {STEP} mumda ({counts['dates']} tarih, "
        f"{candles[START - 1].date} → {candles[len(candles) - LOOKAHEAD - 1].date}); her `t`'de `analyze_levels(candles[:t], "
        f"close_t, pivot_levels=yapısal pivotlar(compute_all(candles[:t], today=tarih_t+1)))` — `assemble._structural_pivots` "
        f"yeniden kullanıldı. Test: sonraki {LOOKAHEAD} mumda fiyat bölgeye {TOUCH_ATR}·ATR_t içine gelir; tepki: temastan "
        f"sonraki {REACTION} kapanış, HOLD ≥ {HOLD_ATR} ATR uzaklaşma ve uzak kenarın ötesinde kapanış yok, BREAK uzak kenarın "
        f"ötesinde ≥ {BREAK_ATR} ATR kapanış, NONE gerisi. Tutma oranı = HOLD / (HOLD + BREAK).\n\n",
        f"Sayım: {counts['zones']} bölge-gün; {counts['unconfirmed_excluded']} onaysız (DEVELOPING) ve "
        f"{counts['testing_excluded']} `testing` (t anında marj içinde) dışarıda; {counts['untested']} bölge 10 mumda test "
        f"edilmedi, {counts['incomplete']} temasın tepki penceresi seride tamamlanmadı; **{len(records)} test edilmiş "
        f"bölge** kaldı ({pooled[0]} HOLD, {pooled[1]} BREAK, {pooled[2]} NONE). Plasebo: {PLACEBO_PER_DATE} rastgele "
        f"seviye/tarih × {counts['dates']} tarih → {len(placebo_outcomes)} test.\n\n",
        "### Temel yapılandırma (yarı ömür "
        f"{base.recency_half_life_days:.0f} g, kanat {base.swing_wing}, eşikler STRONG ≥ {base.strong} / MODERATE ≥ {base.moderate})\n\n",
        md_table(("Kesit", "n", "HOLD", "BREAK", "NONE", "Tutma oranı", "NONE payı"), rows_main),
        f"\nGüç ↔ tutma (0/1, NONE hariç) Pearson korelasyonu: {num(corr, 3)} (n = {len(holds)}). "
        f"Güç dağılımı test edilen bölgelerde: ortanca {statistics.median(strengths):.0f}, "
        f"aralık {min(strengths)}–{max(strengths)}.\n\n",
        "Kesitler (aynı kayıtlar):\n\n",
        md_table(("Kesit", "n", "HOLD", "BREAK", "NONE", "Tutma oranı", "NONE payı"), kind_rows),
        f"\nYoğun örneklem (her mum, {dense_counts['dates']} tarih, pencereler ağır örtüşür — sayı için, bağımsızlık için değil):\n\n",
        md_table(("Kesit", "n", "HOLD", "BREAK", "NONE", "Tutma oranı", "NONE payı"), rows_dense),
        f"\n### Izgara: `recency_half_life_days` × `swing_wing` ({len(grid_rows)} yapılandırma, `dataclasses.replace`, "
        f"paket yapılandırması değişmedi)\n\n",
        md_table(("Yarı ömür", "Kanat", "n test", "Tutma STRONG / MODERATE / WEAK", "n S / M / W",
                  "Tutma T3 / T2 / T1", "Etiket monoton", "Dilim monoton", "Temel"), grid_rows),
        "\n### İleri bakış kanıtı\n\n",
        f"{proof_n} rastgele `t` için `t` sonrası mumlar ±%20 rastgele ölçeklenip karıştırıldı; `t` anındaki bölge "
        f"haritası (`Levels` dataclass'ı, bütün alanlar) **{proof_ok}/{proof_n}** birebir aynı. Aynı boru hattı fonksiyonu "
        f"(`zones_at(seri, t)`) tam seriyle çağrıldığı için sızıntı olsaydı burada görünürdü.\n\n",
        "### Sevk kapısı\n\n",
        f"- Etiket sırası STRONG > MODERATE > WEAK: **{'sağlanıyor' if label_mono else 'sağlanmıyor'}** "
        f"({' / '.join('—' if r is None else f'%{100 * r:.1f}' for r in label_rates)})\n",
        f"- Dilim sırası T3 > T2 > T1: **{'sağlanıyor' if terc_mono else 'sağlanmıyor'}** "
        f"({' / '.join('—' if r is None else f'%{100 * r:.1f}' for r in reversed(terc_rates))})\n",
        f"- En zayıf dilim ≥ plasebo tabanı ({'—' if plac[3] is None else f'%{100 * plac[3]:.1f}'}): "
        f"**{'sağlanıyor' if gate_plac else 'sağlanmıyor'}**; ≥ havuz tabanı "
        f"({'—' if pooled[3] is None else f'%{100 * pooled[3]:.1f}'}): {'sağlanıyor' if gate_pool else 'sağlanmıyor'} "
        f"(havuz dilimlerin ağırlıklı ortalaması olduğu için bu ikincisi ancak dilimler ayrışmadığında sağlanır)\n",
        f"- Yan bazında plasebo: destek bölgeleri {_pct(zone_side['SUPPORT'][3])} ↔ rastgele destek "
        f"{_pct(plac_side['SUPPORT'][3])}; direnç bölgeleri {_pct(zone_side['RESISTANCE'][3])} ↔ rastgele direnç "
        f"{_pct(plac_side['RESISTANCE'][3])} (rejim etkisi: yükselişte destek tutar, direnç kırılır — karşılaştırma "
        f"yan içinde yapılmalı)\n",
        f"- En güçlü dilim (T3) ≥ plasebo: {'evet' if terc_rates and terc_rates[-1] is not None and plac[3] is not None and terc_rates[-1] >= plac[3] else 'hayır'}\n",
        f"- Izgarada etiket sırası {sum(1 for r in grid_rows if r[6] == 'evet')}/{len(grid_rows)}, dilim sırası "
        f"{sum(1 for r in grid_rows if r[7] == 'evet')}/{len(grid_rows)} yapılandırmada monoton\n\n",
    ]
    if gate:
        parts.append("**Sonuç: kapı açık.** Güç etiketi bir iddia olarak sunulabilir (\"güçlü destek\"); yine de "
                     "aşağıdaki örneklem uyarısı geçerlidir.\n")
    else:
        parts.append("**Sonuç: kapı kapalı.** Güç sırası tutma oranına tutarlı biçimde yansımıyor; arayüz gücü "
                     "**betimleyici** göstermeli (\"çok test edildi / az test edildi\", temas sayısı, son temas tarihi, "
                     "kaç kaynağın işaret ettiği), \"güçlü destek → tutar\" iddiası olarak değil.\n")
    parts.append(
        f"\nÖrneklem uyarısı: {len(records)} kayıt {counts['dates']} tarihten geliyor ve aynı bölge ardışık tarihlerde "
        f"tekrar sayılıyor (5 mumluk adım, 10 mumluk ileri pencere → komşu tarihler örtüşür); bağımsız gözlem sayısı "
        f"kayıt sayısının çok altında. Repo dersi: 33 örtüşmeyen 30 günlük pencere gürültüydü. Buradaki yüzdeler "
        f"birkaç puanlık farkı ayırt edemez; yalnız büyük ve ızgara boyunca kararlı farklar anlamlıdır.\n"
        f"\n_Betik süresi {elapsed:.1f} s (temel + plasebo {t_base:.1f} s, ızgara {t_grid:.1f} s)._\n")
    body = "".join(parts)
    print(body)
    path = common.upsert_section("backtest", body)
    print(f"\n→ {path} ({common.doc_size_kb():.1f} KB), elapsed {elapsed:.1f} s")


if __name__ == "__main__":
    main()
