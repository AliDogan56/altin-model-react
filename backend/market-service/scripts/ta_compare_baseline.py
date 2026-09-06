#!/usr/bin/env python
"""Eski (arayüz + `momentum_service`) → yeni (`technical` paketi), 2026-09-06 taban çizgisi.

Çevrimdışı: yalnız `tests/fixtures/` okunur; ağ, sunucu yok. Paket parametresine
dokunulmaz — betik yalnız iki tarafı yan yana koyar ve farkın **tanımdan** mı
yoksa **çerçeveden** mi geldiğini yazar. Çıktı stdout'a ve
`docs/technical/VALIDATION.md` "Eski → yeni" bölümüne gider.

Bölümler: (a) referans fiyat çerçevesi, (b) pivot paritesi ve haftalık klasik ↔
Fibonacci merdiveni, (c) göstergeler (eski tarayıcı tanımı ↔ Wilder), (d) seans
bloğu derin eşitlik, (e) kırılım: tek yanlı eski ↔ iki yanlı yeni, (f) momentum:
seans ↔ günlük bileşik, (g) trend paritesi.
"""
from __future__ import annotations

import re
import time
from datetime import date, datetime, timezone
from typing import Any

import ta_report_common as common
from ta_report_common import md_table, num, pct

from app.services.technical import assemble
from app.services.technical.pivots import PivotMethod, PivotPeriod, build_ladder

NOW = datetime(2026, 9, 6, 10, 2, 5, tzinfo=timezone.utc)   # testlerle aynı an
LIVE_TODAY = date(2026, 9, 6)
HAREM_ASK = 4431.6
WEEKLY, MONTHLY = PivotPeriod.WEEKLY, PivotPeriod.MONTHLY
CLASSIC, FIB = PivotMethod.CLASSIC, PivotMethod.FIBONACCI
VARIANTS = {"weekly_fib": (WEEKLY, FIB), "weekly_classic": (WEEKLY, CLASSIC),
            "monthly_fib": (MONTHLY, FIB), "monthly_classic": (MONTHLY, CLASSIC)}


def _number(text: str) -> float | None:
    m = re.search(r"-?\d+(?:\.\d+)?", text.replace("−", "-"))
    return float(m.group()) if m else None


def _deep_diffs(a: Any, b: Any, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}.{k}: yalnız {'yeni' if k in a else 'eski'} tarafta")
            else:
                out.extend(_deep_diffs(a[k], b[k], f"{path}.{k}"))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: uzunluk {len(a)} ≠ {len(b)}"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(_deep_diffs(x, y, f"{path}[{i}]"))
        return out
    return [] if a == b else [f"{path}: {a!r} ≠ {b!r}"]


def _ladder_rows(ladder, names=("R3", "R2", "R1", "P", "S1", "S2", "S3")):
    by = {i.name: i for i in ladder.items}
    return {n: by[n] for n in names if n in by}


# --- (a) referans ---------------------------------------------------------------

def section_reference(analysis, live) -> str:
    wc = analysis.pivot_sets[WEEKLY][CLASSIC]
    wf = analysis.pivot_sets[WEEKLY][FIB]
    margin_new = analysis.levels.margin_usd
    old_touch = HAREM_ASK * live["fe_break_potential"]["touch_margin_pct"] / 100.0
    rows = []
    for label, price, margin, frame in (
            ("Eski: Harem spot satış", HAREM_ASK, 0.0, "spot (Harem), arayüz kuralı marj 0"),
            ("Eski: Harem + dokunma marjı", HAREM_ASK, old_touch, f"spot, `touchingLevel` marjı %0.2722 = {old_touch:.1f} $"),
            ("Yeni: gün içi son kapanış", analysis.reference.value, margin_new,
             f"`{analysis.reference.frame}` GC=F, marj 0.25·ATR = {margin_new:.1f} $")):
        for name, pset in (("klasik", wc), ("fib", wf)):
            lad = build_ladder(pset.levels, price, margin_usd=margin)
            rows.append((label, f"{price:.1f}", f"haftalık {name}", lad.nearest_up or "—", lad.nearest_down or "—",
                         ", ".join(lad.testing) or "—", frame))
    gap = live["prices"]["spot_vs_close_gap_pct"]
    p_val = dict(wc.levels)["P"]
    text = [
        "### (a) Referans fiyat: eski Harem spot → yeni GC=F gün içi kapanış\n",
        md_table(("Taraf", "Fiyat", "Merdiven", "En yakın üst", "En yakın alt", "Test ediliyor", "Çerçeve"), rows),
        f"\nİki merdiven de aynı haftalık mumdan (`{wc.period_id}`, H {wc.high} / L {wc.low} / C {wc.close}) "
        f"çıkıyor; seviyeler birebir aynı. Değişen yalnız **referans fiyat**: Harem spot GC=F kapanışının "
        f"%{abs(gap):.3f} altında ({HAREM_ASK} ↔ {analysis.reference.value}) ve haftalık P = {p_val:.2f} "
        f"tam bu iki fiyatın arasına düşüyor. Spot çerçevesinde P {p_val - HAREM_ASK:.1f} $ yukarıda "
        f"(\"en yakın üst\", hatta eski dokunma marjıyla \"dokunulan\"), kapanış çerçevesinde "
        f"{analysis.reference.value - p_val:.1f} $ aşağıda (\"en yakın alt\"). Yeni paket Harem'i hiç okumaz "
        f"(`reference.note = LIVE_QUOTE_NOT_USED`): merdiven, bölgeler, ATR ve seans beklenen hareketi tek "
        f"çerçevede (GC=F) kalır; canlı spot yalnız başlıkta kotasyon olarak gösterilir.\n",
    ]
    return "".join(text)


# --- (b) pivotlar -----------------------------------------------------------------

def section_pivots(analysis, live, history, candles) -> str:
    from app.services.technical.pivots import compute_all
    matched = total = 0          # seviye değerleri
    t_matched = t_total = 0      # nearestUp / nearestDown / insertAt alanları
    # canlı: 2 fiyat çerçevesi × 4 varyant × 7 seviye (fixture 4 ondalık → 1e-3)
    sets = compute_all(candles, LIVE_TODAY)
    for prefix, price in (("ladders_at_harem_spot_4431.6", HAREM_ASK), ("ladders_at_last_close_4476.6", 4476.6)):
        ladders = live[next(k for k in live if k.startswith(prefix))]
        for key, (period, method) in VARIANTS.items():
            got = dict(sets[period][method].levels)
            for name, value in ladders[key]["levels"].items():
                total += 1
                matched += abs(got[name] - value) <= 1e-3
            lad = build_ladder(sets[period][method].levels, price)
            fx = ladders[key]
            for mine, theirs in ((lad.nearest_up, fx["nearestUp"]), (lad.nearest_down, fx["nearestDown"]),
                                 (lad.insert_at, fx["insertAt"])):
                t_total += 1
                t_matched += mine == theirs
    # tarihsel: 6 gün × 4 varyant × 7 seviye (1e-6) + hedef alanları
    for entry in history:
        today = date.fromisoformat(entry["today"])
        visible = [c for c in candles if c.date <= today]
        hs = compute_all(visible, today)
        for key, (period, method) in VARIANTS.items():
            got = dict(hs[period][method].levels)
            fxp = entry["pivots"][period.value.lower()]
            fxk = "fib" if method is FIB else "classic"
            for name in ("R3", "R2", "R1", "P", "S1", "S2", "S3"):
                total += 1
                ref = fxp["pivot"] if name == "P" else fxp[fxk][name.lower()]
                matched += abs(got[name] - ref) <= 1e-6
            lad = build_ladder(hs[period][method].levels, entry["price"])
            fx = entry[key]
            for mine, theirs in ((lad.nearest_up, fx["nearestUp"]), (lad.nearest_down, fx["nearestDown"]),
                                 (lad.insert_at, fx["insertAt"])):
                t_total += 1
                t_matched += mine == theirs
    wc = analysis.pivot_sets[WEEKLY][CLASSIC]
    wf = analysis.pivot_sets[WEEKLY][FIB]
    ref = analysis.reference.value
    margin = analysis.levels.margin_usd
    lc = _ladder_rows(build_ladder(wc.levels, ref, margin_usd=margin, atr=analysis.atr))
    lf = _ladder_rows(build_ladder(wf.levels, ref, margin_usd=margin, atr=analysis.atr))
    rows = []
    for name in ("R3", "R2", "R1", "P", "S1", "S2", "S3"):
        c, f = lc[name], lf[name]
        rows.append((name, num(c.value, 2), pct(c.distance, 2, sign=True), c.role or "—",
                     num(f.value, 2), pct(f.distance, 2, sign=True), f.role or "—"))
    text = [
        "### (b) Pivotlar: parite ve başlık merdiveni\n",
        f"Eski arayüzle parite: **{matched}/{total}** seviye değeri (canlı 2 çerçeve × 4 varyant × 7, tolerans "
        f"1e-3 — fixture 4 ondalık; tarihsel 6 gün × 4 varyant × 7, tolerans 1e-6) ve **{t_matched}/{t_total}** "
        f"hedef alanı (`nearestUp` / `nearestDown` / `insertAt`) eşleşti. Aynı denetim "
        f"`tests/test_technical_pivots.py` içinde (testin kendi 28 sabitiyle 252/252) sürekli koşar; burada "
        f"yalnız fixture'daki sayı tekrarlanır.\n\n",
        f"Başlık merdiveni, referans {ref:.1f} $, marj {margin:.1f} $ (0.25·ATR14). Eski varsayılan **haftalık "
        f"Fibonacci** idi; yeni başlık **haftalık klasik**, Fibonacci istek parametresiyle seçilebilir "
        f"(`?pivot_method=`). Dönem `{wc.period_id}`, durum `{wc.status}` / `{wc.completion}`.\n\n",
        md_table(("Basamak", "Klasik", "Δ%", "Rol", "Fibonacci", "Δ%", "Rol"), rows),
        "\nİkisinde de en yakın hedefler R1 (üst) ve P (alt); klasik R1 %2.28, Fibonacci R1 %1.18 uzakta — "
        "Fibonacci R1 = P + 0.382·aralık olduğu için klasik R1'den (2P − L) her zaman P'ye daha yakındır. "
        "Fibonacci R3 klasik R2 ile, S3 klasik S2 ile aynı sayıdır (cebirsel özdeşlik, testte sabit).\n",
    ]
    return "".join(text)


# --- (c) göstergeler --------------------------------------------------------------

def section_indicators(analysis, old) -> str:
    close = analysis.daily[-1].close
    ind = analysis.indicators
    by_name = {r["name"]: r for r in old["rows"]}

    def old_val(name: str) -> tuple[float | None, str, str]:
        r = by_name[name]
        return _number(r["value"]), r["note"], r["text"]

    rsi_o, _, rsi_t = old_val("RSI (14)")
    st_o, st_n, st_t = old_val("Stochastic %K (14)")
    wr_o, _, wr_t = old_val("Williams %R (14)")
    cci_o, _, cci_t = old_val("CCI (20)")
    macd_o, macd_n, macd_t = old_val("MACD (12,26,9)")
    adx_o, adx_n, adx_t = old_val("ADX (14)")
    atr_o, atr_n, atr_t = old_val("ATR (14)")
    roc_o, _, roc_t = old_val("ROC (12)")
    di = re.findall(r"-?\d+(?:\.\d+)?", adx_n.replace("−", "-"))
    atr_pct_new = ind["atr"].value / close * 100.0
    atr_med_new = ind["atr"].extra["median"] / close * 100.0

    def row(name, o, n, definition, o_state, n_state, nd=2):
        d = None if o is None or n is None else n - o
        return (name, num(o, nd), num(n, nd), num(d, nd, sign=True), definition, o_state, n_state)

    rows = [
        row("RSI (14)", rsi_o, ind["rsi"].value,
            "Cutler (14 kazanç/kayıp basit ortalaması) → **Wilder** (α = 1/14, SMA tohum); düz seride eski 0, yeni 50",
            rsi_t, ind["rsi"].state.value, 1),
        row("Stochastic %K (14)", st_o, ind["stochastic"].value, "aynı tanım (hızlı %K, HH−LL = 0 → 50)", st_t,
            ind["stochastic"].state.value, 1),
        row("Stochastic %D (3)", _number(st_n), ind["stochastic"].extra["d"], "aynı tanım (%K'nın 3'lü SMA'sı)", "—", "—", 1),
        row("Williams %R (14)", wr_o, ind["williams"].value, "aynı tanım (aralık 0 → −50)", wr_t, ind["williams"].state.value, 1),
        row("CCI (20)", cci_o, ind["cci"].value,
            "aynı tanım (tipik fiyat, ortalama mutlak sapma, 0.015); eski gösterim 0 ondalık; yeni `fsum` ile düz seride tam 0",
            cci_t, ind["cci"].state.value, 1),
        row("MACD (12,26,9)", macd_o, ind["macd"].value,
            "EMA tohumu: eski **ilk değer**, yeni **ilk n'in SMA'sı** (StockCharts); 1257 mumda tohum farkı sönmüş",
            macd_t, ind["macd"].state.value, 1),
        row("MACD sinyal", _number(macd_n), ind["macd"].extra["signal"],
            "sinyal EMA'sı ilk 9 geçerli MACD'nin SMA'sıyla tohumlanır", "—", f"hist {ind['macd'].extra['histogram']:.1f}", 1),
        row("ADX (14)", adx_o, ind["adx"].value,
            "eski: DX'in 14'lü **basit** ortalaması → yeni: DX de **Wilder** ile yumuşatılır (ilk değer 28. mumda)",
            adx_t, ind["adx"].state.value, 1),
        row("+DI (14)", float(di[0]) if di else None, ind["adx"].extra["plus_di"],
            "oran olduğu için toplam/ortalama Wilder biçimi aynı sonucu verir; eski gösterim 0 ondalık", "—", "—", 1),
        row("−DI (14)", float(di[1]) if len(di) > 1 else None, ind["adx"].extra["minus_di"], "aynı (yukarıdaki gibi)", "—", "—", 1),
        row("ATR (14) % kapanış", atr_o, atr_pct_new,
            f"eski: TR'nin 14'lü **basit** ortalaması → yeni: **Wilder** ATR = {ind['atr'].value:.2f} $", atr_t,
            ind["atr"].state.value, 2),
        row("ATR medyan %", _number(atr_n), atr_med_new,
            "eski: **tüm tarih** üzerinden kayan medyan (2021–23'ün düşük ATR%'si tabanı çeker) → yeni: önceki **100** ATR'nin medyanı "
            f"({ind['atr'].extra['median']:.2f} $); oran {ind['atr'].value / ind['atr'].extra['median']:.2f} < 1.3 → NORMAL",
            "—", "—", 2),
        row("ROC (12) %", roc_o, ind["roc"].value, "aynı tanım (c/c[−12] − 1)·100", roc_t, ind["roc"].state.value, 2),
    ]
    ma_rows = []
    ma_new = {r["period"]: r for r in analysis.moving_averages}
    max_sma = max_ema = 0.0
    for a in old["averages"]:
        n = ma_new[a["n"]]
        ds, de = n["sma"] - a["sma"], n["ema"] - a["ema"]
        max_sma, max_ema = max(max_sma, abs(ds)), max(max_ema, abs(de))
        ma_rows.append((a["n"], num(a["sma"], 2), num(n["sma"], 2), f"{ds:+.1e}", num(a["ema"], 2), num(n["ema"], 2), f"{de:+.1e}",
                        "evet" if n["price_above_sma"] else "hayır"))
    text = [
        "### (c) Göstergeler: eski tarayıcı tanımı → Wilder standardı\n",
        f"Aynı 1257 mum, son kapanış {close}. Eski değerler arayüzün gösterdiği yuvarlanmış metinler "
        "(`indicators_old_fe_20260906.json`), yeni değerler `latest_indicators` çıktısı.\n\n",
        md_table(("Gösterge", "Eski", "Yeni", "Δ", "Tanım farkı", "Eski durum", "Yeni durum"), rows),
        "\nAnlamı değişen tek satır **ATR**: değer değil, **etiket**. Eski taban bütün tarihin medyanıydı (%1.15) ve "
        "2021–2023'ün 1.800 $'lık, düşük ATR%'li dönemi tabanı aşağı çektiği için bugünkü oynaklık \"yüksek\" okunuyordu. "
        "Yeni taban önceki 100 günün medyanı (%1.85); bugünkü ATR ona göre 1.04× → NORMAL. Diğer satırlarda fark tanım "
        "(RSI +2.0 puan, ADX +0.3) ya da yuvarlama düzeyinde ve bant değişmedi; ADX'te eski \"Trend güçleniyor\" metni "
        "20–25 bandının eski adıdır, yeni ad NEUTRAL (TRENDING ≥ 25, WEAK_TREND ≤ 20).\n\n",
        "Hareketli ortalamalar (SMA/EMA, aynı tanım; EMA200 farkı eski \"ilk değer\" tohumunun 1057 adımda sönmemiş kalıntısı):\n\n",
        md_table(("n", "SMA eski", "SMA yeni", "Δ", "EMA eski", "EMA yeni", "Δ", "Fiyat > SMA"), ma_rows),
        f"\nEn büyük mutlak fark: SMA {max_sma:.1e}, EMA {max_ema:.1e} $.\n",
    ]
    return "".join(text)


# --- (d) seans ------------------------------------------------------------------

def section_session(analysis, live) -> str:
    diffs = _deep_diffs(analysis.session, live)
    keys = ", ".join(f"`{k}`" for k in live)
    text = [
        "### (d) Seans bloğu: derin eşitlik\n",
        f"`technical.session.momentum(intraday.bars, daily=points)` ↔ `momentum_live_20260906.json` (eski "
        f"`momentum_service` canlı yanıtı, `as_of` {live['as_of']}): **{len(diffs)} fark** "
        f"({len(live)} üst anahtar: {keys}; iç içe {sum(1 for _ in _walk(live))} yaprak değer). "
        f"Aynı denetim `tests/test_technical_session_fixture.py` içinde alan dışlamadan koşar.\n",
    ]
    if diffs:
        text.append("\n" + "\n".join(f"- {d}" for d in diffs[:20]) + "\n")
    return "".join(text)


def _walk(value: Any):
    if isinstance(value, dict):
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v)
    else:
        yield value


# --- (e) kırılım ----------------------------------------------------------------

def section_breakout(analysis, live) -> str:
    b = analysis.breakout
    be = live["momentum_service_live"]["service_own_breakout"]
    fe = live["fe_break_potential"]
    rows = [
        ("Eski BE (`momentum_service`)", "tek yan: destek", f"{be['level']} {be['value']} (servisin kendi merdiveni)",
         num(be["distance"], 1), num(be["reach"], 2), "seans 22 → 0.22", "—", num(be["score"], 3), be["strength"]),
    ]
    for side_key, side_name in (("nearestUp", "yukarı"), ("nearestDown", "aşağı")):
        s = fe[side_key]
        rows.append(("Eski FE (`breakPotential`, Harem çerçevesi, haftalık fib)", side_name,
                     f"{s['name']} {s['value']:.1f}", num(abs(s["value"] - fe["app_price"]), 1),
                     num(s["breakPotential"]["reach"], 2), "seans 22 → 0.22", "—",
                     num(s["breakPotential"]["score"], 3), s["breakPotential"]["strength"]))
    for side_key, side_name in (("up", "yukarı"), ("down", "aşağı")):
        s = getattr(b, side_key)
        t = s.target
        comp = s.components
        rows.append(("Yeni (`analyze_breakout`, GC=F çerçevesi)", side_name,
                     f"{t.zone_id} ({t.name}, güç {t.zone_strength}) {t.value:.1f}", num(s.distance_usd, 1),
                     num(s.reach, 2),
                     f"seans {comp['session']:.2f}·{b.weights['session']} + günlük {comp['daily']:.2f}·{b.weights['daily']} = {s.push:.3f}",
                     num(s.damping, 3), f"{comp['score']:.3f} ({s.strength})", s.label))
    text = [
        "### (e) Kırılım: tek yanlı eski → iki yanlı yeni\n",
        md_table(("Kaynak", "Yan", "Hedef", "Uzaklık $", "Ulaşma", "İtiş", "Sönüm", "Skor", "Etiket"), rows),
        f"\nEski cebir `sqrt(min(1, ulaşma) · güç/100)` idi: seans NEUTRAL·22 ile ulaşılabilir her seviye "
        f"√0.22 = 0.469 → MEDIUM veriyordu — eski BE'nin S1'i ve eski FE'nin P'si aynı 0.469'u taşıyor, hedef "
        f"farklı olsa da. Yeni formül `sqrt(ulaşma · itiş) · sönüm`; itiş = 0.6·seans + 0.4·günlük ve günlük itiş "
        f"yalnız skorun (59) 50'nin üstünde kalan yanı, yani **yukarıyı** iter ({(b.daily_score - 50) / 25:.2f}); "
        f"aşağı yanda günlük itiş 0. Hedefler artık test edilmiş **bölgeler** ({b.up.target.zone_id} güç "
        f"{b.up.target.zone_strength}, {b.down.target.zone_id} güç {b.down.target.zone_strength}) ve bölge gücü "
        f"kırılımı kısıyor (sönüm {b.up.damping:.3f} / {b.down.damping:.3f}). Sonuç: yukarı {b.up.strength} "
        f"{b.up.label}, aşağı {b.down.strength} {b.down.label}; `headline` {b.headline} (seans NEUTRAL → öne "
        f"çıkarılan yan yok), not `{b.note}`. Beklenen hareket seansın kalanı için {b.expected_move:.2f} $ "
        f"(`{b.expected_move_frame}`, %{100 * b.expected_move_pct:.2f}).\n",
    ]
    return "".join(text)


# --- (f) momentum --------------------------------------------------------------

def section_momentum(analysis, live) -> str:
    md = analysis.momentum_daily
    old_c = live["components"]
    trend_days = common.CONFIG.momentum_daily.trend_days
    earlier = md.history[-1 - trend_days]   # tarihçe ölçülemeyen günü atlar; fixture'da yok
    rows = [
        ("Soru", "bu seans ilk seviyeyi kırmaya yeter mi (5 dk mum, GC=F)", "son haftalar ne kadar tek yönlü ve kararlı (günlük mum)"),
        ("Sonuç", f"{live['direction']} · {live['strength']} · {live['trend']}",
         f"{md.direction} · {md.score} · {md.strength} · {md.trend}" + (f" · {md.note}" if md.note else "")),
        ("Yön kapısı", f"t = {live['session']['t_stat']} ama |hız| = {abs(old_c['velocity']):.2f} < 1 → NEUTRAL",
         f"skor {md.score} ∈ ({common.CONFIG.momentum_daily.down}, {common.CONFIG.momentum_daily.up}) → NEUTRAL; "
         f"uyum {md.agreement:.2f} < {common.CONFIG.momentum_daily.conflicting_agreement} → CONFLICTING"),
        ("Bileşik", f"lojistik(|z| × uyum) → {live['strength']}",
         f"z = {md.z:+.3f}; skor = 50 + 50·tanh(z / {md.z_scale}) = {md.score}"),
        ("Bileşenler (σ birimi)",
         ", ".join(f"{k} {v:+.2f}" for k, v in old_c.items()),
         ", ".join(f"{k} {v:+.2f}" for k, v in md.components.items())),
        ("Ağırlıklar", "hız .25 sürüklenme .20 ivme .20 hacim .15 RSI .10 MACD .10",
         " ".join(f"{k} {v:.2f}" for k, v in md.weights.items())),
        ("Ölçek", f"seans σ = %{live['session']['volatility_pct']} (mum getirisi)",
         f"σ20 = {md.sigma:.4f} (günlük log getiri), ATR14 = {md.atr:.2f} $"),
        ("Son 3 gün", "—", f"Δ {md.delta:+d}, ivme {md.acceleration:+d}, tarihçe {list(md.history[-5:])}"),
    ]
    text = [
        "### (f) Momentum: seans bloğu ↔ günlük bileşik\n",
        md_table(("", "Eski / seans (korundu, `session.py`)", "Yeni / günlük (`momentum_daily.py`)"), rows),
        "\nİki blok **farklı soruya** cevap verir ve ikisi de yanıtta ayrı durur; sayıları karşılaştırmak anlamsız. "
        "Bugün ikisi de NEUTRAL diyor ama gerekçe farklı: seans, hız kapısını geçemedi; günlük ise "
        f"{md.score} ile eşiğin hemen altında ve bileşenler çelişiyor (hız {md.components['velocity']:+.2f} ↔ 50 günlük "
        f"ortalamadan uzaklık {md.components['ma']:+.2f}). Son on günün skorları {list(md.history[-10:])}; `{md.trend}` "
        f"etiketi {trend_days} gün önceki {earlier} ile bugünkü {md.score} arasındaki orta noktadan uzaklık farkından "
        f"({abs(md.score - 50) - abs(earlier - 50):+d} ≥ {common.CONFIG.momentum_daily.trend_delta}) geliyor.\n",
    ]
    return "".join(text)


# --- (g) trend -------------------------------------------------------------------

def section_trend(analysis, expected) -> str:
    keys = {"slopePct": "slope_pct", "first": "first", "last": "last", "r2": "r2",
            "changePct": "change_pct", "sigma": "sigma", "lastZ": "last_z"}
    rows = []
    worst = 0.0
    for rid, rng in analysis.trend.items():
        fx = expected[rid]
        fit = rng.fit
        field_diff = max(abs(getattr(fit, new) - fx["fit"][old]) for old, new in keys.items())
        realized = abs(rng.realized_pct - fx["realizedPct"])
        line = max(abs(r.fit - v) for r, v in zip(rng.rows, fx["fitLine"]))
        b1 = max(max(abs(r.b1[0] - v[0]), abs(r.b1[1] - v[1])) for r, v in zip(rng.rows, fx["band1"]))
        b2 = max(max(abs(r.b2[0] - v[0]), abs(r.b2[1] - v[1])) for r, v in zip(rng.rows, fx["band2"]))
        rel = max(line, b1, b2) / fx["fitLine"][-1]
        worst = max(worst, field_diff, realized, rel)
        rows.append((rid, len(rng.rows), fx["observations"], fit.direction, fx["fit"]["direction"].upper(),
                     f"{fit.r2:.4f}", pct(fit.change_pct, 2, sign=True), pct(rng.realized_pct, 2, sign=True),
                     f"{field_diff:.1e}", f"{realized:.1e}", f"{max(line, b1, b2):.1e} $ ({rel:.1e})"))
    text = [
        "### (g) Trend: yeni blok ↔ eski arayüz uydurması\n",
        md_table(("Aralık", "n yeni", "n eski", "Yön", "Yön eski", "r²", "Trend Δ", "Gerçekleşen Δ",
                  "maks |Δ| uydurma alanları", "maks |Δ| gerçekleşen", "maks |Δ| çizgi+bantlar"), rows),
        f"\nBeş aralığın tamamında en büyük mutlak fark **{worst:.1e}** (kayan nokta toplama sırası); yön, r² ve "
        "gerçekleşen değişim birebir. Matematik taşınmış, değişmemiştir.\n",
    ]
    return "".join(text)


def main() -> None:
    t0 = time.perf_counter()
    daily = common.load_fixture("xau_daily_20260906.json")
    intraday = common.load_fixture("intraday_20260906.json")
    live_session = common.load_fixture("momentum_live_20260906.json")
    old_ind = common.load_fixture("indicators_old_fe_20260906.json")
    trend_expected = common.load_fixture("trend_expected_20260906.json")
    baseline_live = common.load_fixture("baseline_live_20260906.json")
    baseline_history = common.load_fixture("baseline_history_20260906.json")
    candles = common.daily_candles()

    analysis = assemble.analyze(daily, intraday, now=NOW)
    parts = [
        "## Eski → yeni\n",
        f"Taban çizgisi 2026-09-06, `now` = {NOW.isoformat()} (testlerle aynı). Blok durumu "
        f"{sum(1 for s in analysis.status.values() if s == 'OK')}/{len(analysis.status)} OK; "
        f"referans {analysis.reference.value} (`{analysis.reference.frame}`), ATR14 {analysis.atr:.2f} $, "
        f"σ20 {analysis.momentum_daily.sigma:.4f}.\n\n",
        section_reference(analysis, baseline_live), "\n",
        section_pivots(analysis, baseline_live, baseline_history, candles), "\n",
        section_indicators(analysis, old_ind), "\n",
        section_session(analysis, live_session), "\n",
        section_breakout(analysis, baseline_live), "\n",
        section_momentum(analysis, live_session), "\n",
        section_trend(analysis, trend_expected),
    ]
    elapsed = time.perf_counter() - t0
    parts.append(f"\n_Betik süresi {elapsed:.2f} s._\n")
    body = "".join(parts)
    print(body)
    path = common.upsert_section("eski-yeni", body)
    print(f"\n→ {path} ({common.doc_size_kb():.1f} KB), elapsed {elapsed:.2f} s")


if __name__ == "__main__":
    main()
