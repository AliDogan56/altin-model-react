"""Betik girdileri: modele 'neden' sorusunun malzemesini hazır verir (web araması yerine).

- faiz_beklentisi: fed funds vadelisi (Yahoo ZQ) + FRED EFFR / hedef bant → bir sonraki FOMC için ima edilen +25bp olasılığı
- enflasyon: FRED TÜFE serilerinden aylık ve yıllık değişim (manşet ve çekirdek)
- takvim: calendar.toml (CALENDAR_PATH) → önümüzdeki N gün ve bugünün olayları
- pozisyon: CFTC Socrata → altın yönetilen para net pozisyonu, haftalık değişim, 3 yıllık yüzdelik
- haberler: Google News RSS, birden çok sorgu, tekilleştirilmiş
Her blok kaynak ve zaman taşır; alınamayan blok {"veri": "yok", "hata": ...} döner, uydurulmaz.
"""
from __future__ import annotations

import datetime as dt
import io
import tomllib

import pandas as pd

from ..market_constants import CALENDAR_PATH, MACRO_CSV
from .http_client import get_json, get_text
from .news_service import parse_rss

AY_KODU = "FGHJKMNQUVXZ"


def _fred_son(series: str) -> tuple[dt.date, float]:
    t = get_text(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}", impersonate=True)
    df = pd.read_csv(io.StringIO(t))
    df.columns = ["d", "v"]
    df["v"] = pd.to_numeric(df["v"], errors="coerce")
    df = df.dropna()
    return pd.Timestamp(df["d"].iloc[-1]).date(), float(df["v"].iloc[-1])


def _zq(year: int, month: int) -> float | None:
    sym = f"ZQ{AY_KODU[month - 1]}{str(year)[2:]}.CBT"
    try:
        m = get_json(f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d")["chart"]["result"][0]["meta"]
        return float(m["regularMarketPrice"])
    except Exception:  # noqa: BLE001
        return None


def fomc_dates() -> list[dict]:
    p = CALENDAR_PATH
    if not p.exists():
        return []
    with open(p, "rb") as f:
        return [o for o in tomllib.load(f).get("olay", []) if o.get("tur") == "fomc"]


def rate_expectations(bugun: dt.date | None = None) -> dict:
    bugun = bugun or dt.datetime.now(dt.UTC).date()
    try:
        effr_d, effr = _fred_son("EFFR")
        _, ust = _fred_son("DFEDTARU")
        _, alt = _fred_son("DFEDTARL")
        gelecek = [o for o in fomc_dates() if dt.date.fromisoformat(o["tarih"]) >= bugun]
        if not gelecek:
            return {"veri": "yok", "hata": "takvimde gelecek FOMC yok"}
        top = dt.date.fromisoformat(gelecek[0]["tarih"])
        ay_gun = (dt.date(top.year + (top.month == 12), (top.month % 12) + 1, 1) - dt.date(top.year, top.month, 1)).days
        sonraki = top.day  # toplantı gününden sonraki günler: ay_gun - top.day
        p_ay = _zq(top.year, top.month)
        nxt = dt.date(top.year + (top.month == 12), (top.month % 12) + 1, 1)
        p_sonraki = _zq(nxt.year, nxt.month)
        out = {"kaynak": "Yahoo fed funds vadelisi (ZQ) + FRED EFFR/DFEDTAR", "nasil_anilir": "vadeli işlem fiyatlarından türetilen olasılık; bir haber kaynağına ya da FedWatch'a bağlama", "tarih": str(effr_d), "efektif_faiz": effr, "hedef_bant": [alt, ust], "toplanti": str(top),
               "yontem": "CME benzeri: (kontratın ima ettiği ay ortalaması − mevcut efektif faiz) ÷ (0,25 × toplantı sonrası gün payı); 0–100 arasında kırpılır. Kaba bir ölçüdür, resmi FedWatch değildir."}
        if p_ay is not None:
            ima = 100 - p_ay
            pay = (ay_gun - sonraki) / ay_gun
            p25 = (ima - effr) / (0.25 * pay) if pay > 0 else None
            out["toplanti_ayi_kontrati"] = {"ima_edilen_ortalama": round(ima, 3), "artis_25bp_olasiligi_pct": None if p25 is None else round(max(0.0, min(100.0, p25 * 100)), 0)}
        if p_sonraki is not None:
            ima2 = 100 - p_sonraki
            out["sonraki_ay_kontrati"] = {"ima_edilen_ortalama": round(ima2, 3), "toplam_degisim_bp": round((ima2 - effr) * 100, 0)}
        return out
    except Exception as exc:  # noqa: BLE001
        return {"veri": "yok", "hata": str(exc)[:160]}


def inflation() -> dict:
    if not MACRO_CSV.exists():
        return {"veri": "yok", "hata": "macro_obs.csv yok"}
    m = pd.read_csv(MACRO_CSV, parse_dates=["obs_date"])
    out = {"kaynak": "FRED CPIAUCSL / CPILFESL (mevsimsellikten arındırılmış endeks)", "not": "Piyasa beklentisi verisi yok; sürpriz değerlendirmesi yapılamaz."}
    for sid, ad in (("CPIAUCSL", "manset"), ("CPILFESL", "cekirdek")):
        g = m[m["series"] == sid].sort_values("obs_date")
        if len(g) < 14:
            continue
        v = g["value"].to_numpy()
        out[ad] = {"ay": g["obs_date"].iloc[-1].strftime("%Y-%m"), "aylik_pct": round((v[-1] / v[-2] - 1) * 100, 2), "onceki_aylik_pct": round((v[-2] / v[-3] - 1) * 100, 2), "yillik_pct": round((v[-1] / v[-13] - 1) * 100, 2)}
    return out


def calendar_events(gun: int = 14, bugun: dt.date | None = None) -> dict:
    bugun = bugun or dt.datetime.now(dt.UTC).date()
    p = CALENDAR_PATH
    if not p.exists():
        return {"veri": "yok", "hata": f"takvim dosyası yok: {CALENDAR_PATH}"}
    with open(p, "rb") as f:
        olaylar = tomllib.load(f).get("olay", [])
    yakin = []
    for o in olaylar:
        d = dt.date.fromisoformat(o["tarih"])
        kalan = (d - bugun).days
        if 0 <= kalan <= gun:
            saat_tr = None
            if o.get("saat_utc"):
                hh, mm = o["saat_utc"].split(":")
                saat_tr = f"{(int(hh) + 3) % 24:02d}:{mm}"
            yakin.append({"ad": o["ad"], "tarih": o["tarih"], "saat_utc": o.get("saat_utc"), "saat_turkiye": saat_tr, "kac_gun_sonra": kalan, "bugun": kalan == 0})
    return {"kaynak": "calendar.toml (Fed resmi FOMC takvimi)", "pencere_gun": gun, "olaylar": yakin}


def positioning() -> dict:
    try:
        url = ("https://publicreporting.cftc.gov/resource/72hh-3qpy.json?$where=upper(market_and_exchange_names) like '%25GOLD - COMMODITY EXCHANGE%25'"
               "&$order=report_date_as_yyyy_mm_dd DESC&$limit=400")
        rows = get_json(url)
        df = pd.DataFrame(rows)
        for c in ("m_money_positions_long_all", "m_money_positions_short_all", "open_interest_all"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["tarih"] = pd.to_datetime(df["report_date_as_yyyy_mm_dd"]).dt.date
        # aynı tarihte birden çok satır olabilir (COMEX altın alt sözleşmeleri); en büyük açık pozisyonlu satırı al
        df = df.sort_values(["tarih", "open_interest_all"], ascending=[False, False]).drop_duplicates("tarih").sort_values("tarih")
        df["net"] = df["m_money_positions_long_all"] - df["m_money_positions_short_all"]
        son = df.iloc[-1]
        uc_yil = df[df["tarih"] >= son["tarih"] - dt.timedelta(days=3 * 365)]
        yuzdelik = float((uc_yil["net"] < son["net"]).mean() * 100)
        return {"kaynak": "CFTC Disaggregated Futures Only (Socrata 72hh-3qpy), COMEX altın, yönetilen para", "rapor_tarihi": str(son["tarih"]),
                "net_uzun": int(son["net"]), "uzun": int(son["m_money_positions_long_all"]), "kisa": int(son["m_money_positions_short_all"]),
                "haftalik_degisim": int(son["net"] - df.iloc[-2]["net"]) if len(df) > 1 else None, "acik_pozisyon": int(son["open_interest_all"]),
                "uc_yil_yuzdelik": round(yuzdelik, 0), "okuma": "kalabalık" if yuzdelik >= 80 else ("seyrek" if yuzdelik <= 20 else "orta")}
    except Exception as exc:  # noqa: BLE001
        return {"veri": "yok", "hata": str(exc)[:160]}


SORGULAR = [
    ("gold+price+Fed", "en"), ("gold+site:reuters.com", "en"), ("gold+site:kitco.com", "en"), ("gold+prices+today", "en"), ("ons+alt%C4%B1n", "tr"),
]


def fetch_headlines(saat: int = 24, en_fazla: int = 10) -> list[dict]:
    esik = dt.datetime.now(dt.UTC) - dt.timedelta(hours=saat)
    hepsi, gorulen = [], set()
    for q, dil in SORGULAR:
        url = f"https://news.google.com/rss/search?q={q}&hl={'tr' if dil == 'tr' else 'en-US'}&gl={'TR' if dil == 'tr' else 'US'}&ceid={'TR:tr' if dil == 'tr' else 'US:en'}"
        try:
            for h in parse_rss(get_text(url, timeout=20), dil):
                try:
                    if dt.datetime.fromisoformat(h["zaman_utc"]) < esik:
                        continue
                except Exception:  # noqa: BLE001
                    pass
                anahtar = h["baslik"].lower()[:60]
                if anahtar in gorulen:
                    continue
                gorulen.add(anahtar)
                hepsi.append({"baslik": h["baslik"][:140], "kaynak": h["kaynak"], "zaman_utc": h["zaman_utc"]})
        except Exception:  # noqa: BLE001
            continue
    hepsi.sort(key=lambda h: h["zaman_utc"], reverse=True)
    return hepsi[:en_fazla]


def collect_market_inputs(bugun: dt.date | None = None) -> dict:
    return {"faiz_beklentisi": rate_expectations(bugun), "enflasyon": inflation(), "takvim": calendar_events(14, bugun), "pozisyon": positioning()}
