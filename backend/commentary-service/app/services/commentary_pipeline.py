"""Ajan rolleri, araçsız: her rol betiklerin hazırladığı girdi paketini okur, tek LLM çağrısıyla çıktısını verir.

Rol istemleri app/prompts/<rol>.md gövdesinden gelir; araç gerektiren bölümler atılır, kurallar kalır.
Tam tur: technical_analyst → calendar_news_scout → macro_analyst → chief_analyst → anchor. Hızlı tur: yalnız anchor
(son tam turun brifiyle). Paket ve şema anahtarları bilerek Türkçedir: model Türkçe yazar ve denetim aynı anahtarları okur;
dış API sözleşmesi (commentary_store) İngilizcedir.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time

import pandas as pd

from ..config import settings
from ..market_constants import LATEST_DIR, MACRO_CSV, MARKET_CSV, PROMPTS_DIR
from . import market_inputs_service as market_inputs
from .llm_config import LlmSettings
from .llm_gateway import TokenUsage, ask, parse_json
from .output_audit import audit_text
from . import commentator_service

NO_TOOLS_NOTE = """

## Bu ortamda araç yok
Dosya, betik ve web yok; bütün girdi aşağıdaki pakettir.

## Sayı ve dil kuralları (betik denetler)
- Yalnız pakette geçen sayıları kullan; yuvarlayabilirsin (4295,09 → 4.295; 2,28 → 2,3). Pakette olmayan olasılık, oran,
  tarih ya da fiyat yazma.
- Sayılar rakamla ve Türkçe biçimde: "4.295 dolar", "yüzde 2,3"; sözcükle sayı yazma.
- Yasak kısaltmalar: ATR, SMA, EMA, RSI, MACD, ADX, VIX, DXY, Dow, FOMC, Fed, TIPS, COT, GVZ, PAXG, LBMA. Sade karşılık:
  "günlük olağan dalgalanma", "son 50 günün ortalaması", "trend gücü", "borsadaki korku ölçüsü" (yalnız VIX için),
  "dolar endeksi", "zirveler ve dipler", "Amerikan Merkez Bankası'nın faiz toplantısı", "reel faiz", "Londra resmi fiksi".
- Fiyatın altındaki seviye destek, üstündeki dirençtir; kırılan destek yukarıda tavan olur. Ters yazma.
- Reel faiz ve dolar yükselişi altın için aleyhtedir; düşüşü lehtedir.
- Yön iddiası yok; masa yön vermiyorsa bunu söyle. Rol tanımını metne kopyalama; "masa" de, "ben" deme.
- Saatler Türkiye saatiyle (paketteki `saat_turkiye`); UTC yazma.
- Faiz artışı olasılığı `faiz_beklentisi` bloğundan gelir; "vadeli işlem fiyatlarından türetilen olasılık" diye anılır."""

# Teknik role giden gösterge sözlüğü: model açıklama uydurmasın (ölçüldü: ADX "korku ölçüsü" diye anlatılmıştı).
SOZLUK = {
    "momentum.skor": "−100..+100; sıfır çevresi nötr, mutlak 40 üstü belirgin",
    "hizalanma": "günlük/haftalık/aylık momentum aynı yönde mi; karisik = yön belirsiz",
    "dow": "zirve ve diplerin sırası: yükseliş / düşüş / belirsiz",
    "sma50_pct, sma200_pct": "fiyatın 50 ve 200 günlük ortalamaya göre yüzde uzaklığı",
    "adx14": "trend gücü ölçüsü, yön söylemez; 25 altı zayıf, 40 üstü güçlü trend",
    "destek_cizgisi, direnc_cizgisi": "son diplerden / tepelerden geçen trend çizgisi; bugünkü değeri, temas sayısı, kırıldı mı",
    "kanal_250": "250 günlük regresyon kanalında konum (σ) ve uyum (r²); betimsel, sinyal değil",
    "seviyeler_canli": "canlı fiyata göre en yakın dirençler/destekler; kaynak_sayisi = kaç yöntem aynı yere işaret ediyor",
    "gecersizleme_spot": "hangi kapanış tezi bozar",
    "taban_koni_80": "ufuk başına yüzde 80 olasılık aralığı (p10–p90); tahmin değil, oynaklık ölçüsü",
    "basis": "vadeli fiyatın spota oranı; seviyeler spot eşdeğer",
}

TAKVIM_SCHEMA = {
    "type": "object",
    "properties": {
        "takvim": {"type": "array", "items": {"type": "object", "properties": {"tarih": {"type": "string"}, "saat_turkiye": {"type": "string"}, "olay": {"type": "string"}, "onem": {"type": "string"}}, "required": ["tarih", "saat_turkiye", "olay", "onem"], "additionalProperties": False}},
        "haberler": {"type": "array", "items": {"type": "object", "properties": {"baslik": {"type": "string"}, "kaynak": {"type": "string"}, "iddia": {"type": "string"}}, "required": ["baslik", "kaynak", "iddia"], "additionalProperties": False}},
        "surpriz": {"type": "string"}, "bugun_cumle": {"type": "string"},
    },
    "required": ["takvim", "haberler", "surpriz", "bugun_cumle"], "additionalProperties": False,
}

SUNUM_SCHEMA = {
    "type": "object",
    "properties": {
        "baslik": {"type": "string"}, "manset": {"type": "string"}, "ozet": {"type": "string"},
        "bolumler": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string", "enum": ["giris", "neden", "masa", "seviyeler", "buyuk_resim", "sesler", "takvim", "kapanis"]},
            "baslik": {"type": "string"}, "metin": {"type": "string"}}, "required": ["id", "baslik", "metin"], "additionalProperties": False}},
    },
    "required": ["baslik", "manset", "ozet", "bolumler"], "additionalProperties": False,
}
MAKRO_SCHEMA = {
    "type": "object",
    "properties": {
        "piyasa_anlatisi": {"type": "object", "properties": {"ozet": {"type": "string"}, "masanin_gorusu": {"type": "string"}}, "required": ["ozet", "masanin_gorusu"], "additionalProperties": False},
        "suruculer": {"type": "array", "items": {"type": "object", "properties": {"surucu": {"type": "string"}, "altin_icin": {"type": "string", "enum": ["lehine", "aleyhine", "karisik"]}, "guc": {"type": "integer"}, "kanit": {"type": "string"}}, "required": ["surucu", "altin_icin", "guc", "kanit"], "additionalProperties": False}},
    },
    "required": ["piyasa_anlatisi", "suruculer"], "additionalProperties": False,
}
BRIF_SCHEMA = {
    "type": "object",
    "properties": {
        "baslik": {"type": "string"}, "tez": {"type": "string"},
        "yon": {"type": "string", "enum": ["yukselis", "dusus", "notr", "belirsiz"]},
        "guven": {"type": "string", "enum": ["dusuk", "orta", "yuksek"]},
        "ana_noktalar": {"type": "array", "items": {"type": "string"}},
        "riskler": {"type": "array", "items": {"type": "string"}},
        "celiskiler": {"type": "array", "items": {"type": "object", "properties": {"konu": {"type": "string"}, "taraflar": {"type": "string"}, "tercih": {"type": "string"}}, "required": ["konu", "taraflar", "tercih"], "additionalProperties": False}},
        "veri_uyarilari": {"type": "array", "items": {"type": "string"}},
        "takvim_one_cikan": {"type": "array", "items": {"type": "string"}},
        "bugun": {"type": "object", "properties": {"cumle": {"type": "string"}}, "required": ["cumle"], "additionalProperties": False},
        "piyasa_anlatisi": {"type": "object", "properties": {"ozet": {"type": "string"}, "altina_etkisi": {"type": "string"}, "masanin_gorusu": {"type": "string"}}, "required": ["ozet", "altina_etkisi", "masanin_gorusu"], "additionalProperties": False},
        "piyasa_sesleri": {"type": "string"},   # yorumcu gözcüsü kaydı varsa en fazla iki cümle, yoksa boş dize
    },
    "required": ["baslik", "tez", "yon", "guven", "ana_noktalar", "riskler", "celiskiler", "veri_uyarilari", "takvim_one_cikan", "bugun", "piyasa_anlatisi", "piyasa_sesleri"], "additionalProperties": False,
}



# Çalışma zamanı istemleri (app/prompts) yalnız modele gidecek bölümleri taşır; bu liste eski ajan biçimindeki
# dosyalar için emniyettir. "Çıktı"/"Çıktılar" bilerek yok: kural taşıyan bölümler modele ulaşmalı.
SKIPPED_SECTIONS = ("Girdiler", "Adımlar", "Durum", "Hedef arayüz", "Eşleme")


def role_prompt(role_name: str) -> str:
    """Rol gövdesi; araç ve dosya odaklı bölümler atılır, kurallar kalır."""
    md = (PROMPTS_DIR / f"{role_name}.md").read_text()
    md = re.sub(r"^---.*?---\s*", "", md, flags=re.S)
    parts = re.split(r"(?m)^(?=## )", md)
    kept = [x for x in parts if not any(x.startswith(f"## {b}") for b in SKIPPED_SECTIONS)]
    return "".join(kept).strip() + NO_TOOLS_NOTE


def _j(name: str):
    p = LATEST_DIR / name
    return json.loads(p.read_text()) if p.exists() else None


def _md(name: str) -> str | None:
    p = LATEST_DIR / name
    return p.read_text() if p.exists() else None


def macro_changes() -> dict:
    """Betikle: her FRED serisi için son değer ve 5/20 gözlemlik değişim; piyasa serileri için de."""
    out = {}
    if MACRO_CSV.exists():
        m = pd.read_csv(MACRO_CSV, parse_dates=["obs_date"])
        for sid, g in m.groupby("series"):
            v = g.sort_values("obs_date")["value"].dropna()
            if len(v) < 21:
                continue
            out[sid] = {"son": round(float(v.iloc[-1]), 3), "d5": round(float(v.iloc[-1] - v.iloc[-6]), 3), "d20": round(float(v.iloc[-1] - v.iloc[-21]), 3), "son_tarih": g.sort_values("obs_date")["obs_date"].iloc[-1].strftime("%Y-%m-%d")}
    if MARKET_CSV.exists():
        mk = pd.read_csv(MARKET_CSV, parse_dates=["date"])
        for col in mk.columns:
            if col == "date":
                continue
            v = mk[col].dropna()
            if len(v) < 21:
                continue
            out[col] = {"son": round(float(v.iloc[-1]), 3), "d5_pct": round(float(v.iloc[-1] / v.iloc[-6] - 1) * 100, 2), "d20_pct": round(float(v.iloc[-1] / v.iloc[-21] - 1) * 100, 2)}
    return out


KAYNAK_ADI = (("PAXG", "spot izleyen seri"), ("GC=F", "vadeli altın"), ("LBMA", "Londra resmi fiksi"))


def plain_source(name: str | None) -> str | None:
    """Kaynak kodlarını sade karşılığa çevirir; yasak terim denetimi paketin kendisine takılmasın."""
    if not name:
        return name
    for code, plain in KAYNAK_ADI:
        if code.lower() in name.lower():
            return plain
    return name


def turkiye_saati(iso_utc: str | None) -> str | None:
    if not iso_utc:
        return None
    try:
        return dt.datetime.fromisoformat(iso_utc).astimezone(dt.timezone(dt.timedelta(hours=3))).strftime("%H:%M")
    except ValueError:
        return None


def base_package() -> dict:
    snap, lv, mom, trend, cone, fresh = (_j(n) for n in ("snapshot.json", "levels.json", "momentum.json", "trend.json", "base_cone.json", "freshness.json"))
    if not snap or not lv:
        raise RuntimeError("snapshot/levels yok: önce snapshot_service.build_snapshot çalışmalı")
    canli = lv.get("canli") or {}
    canli_snap = dict(snap.get("canli") or {})
    if canli_snap.get("kaynak"):
        canli_snap["kaynak"] = plain_source(canli_snap["kaynak"])
    slim = lambda xs: [{"spot_esdeger": x["spot_esdeger"], "kaynak_sayisi": x["kaynak_sayisi"], "uzaklik_pct": x.get("canli_uzaklik_pct", x.get("uzaklik_pct"))} for x in xs[:3]]  # noqa: E731
    tl = (trend or {}).get("trend_cizgileri") or {}
    cizgi = lambda ln: None if not ln else {"bugun_spot": ln.get("bugunku_deger_spot"), "temas": ln.get("temas"), "kirildi": ln.get("kirildi")}  # noqa: E731
    kanal = ((trend or {}).get("regresyon_kanali") or {}).get("250")
    return {
        "as_of": snap["as_of"], "simdi_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "canli": canli_snap or None, "canli_zaman_utc": snap.get("canli_zaman_utc"), "saat_turkiye": turkiye_saati(snap.get("canli_zaman_utc")), "basis": snap.get("basis"),
        "resmi_fiks": snap["spot_lbma_pm"], "vadeli": snap["vadeli_gcf"],
        "seviyeler_canli": {k: slim(canli.get(k, [])) for k in ("direnc", "destek", "test_edilen", "bugun_gecilen")},
        "momentum": {k: {"skor": v["skor"], "etiket": v["etiket"], "son_bar": (mom or {}).get("son_bar", {}).get(k), "en_guclu": sorted(((n, c["skor"]) for n, c in v["bilesenler"].items() if c["skor"] is not None), key=lambda x: -abs(x[1]))[:1]} for k, v in (mom or {}).get("cerceveler", {}).items()},
        "hizalanma": ((mom or {}).get("hizalanma") or {}).get("durum"),
        "trend": {"dow": ((trend or {}).get("dow") or {}).get("durum"), "sma50_pct": ((trend or {}).get("ortalamalar") or {}).get("fiyat_sma50_pct"), "sma200_pct": ((trend or {}).get("ortalamalar") or {}).get("fiyat_sma200_pct"), "adx14": (trend or {}).get("adx14"),
                  "destek_cizgisi": cizgi(tl.get("destek")), "direnc_cizgisi": cizgi(tl.get("direnc")), "kanal_250": {"konum_sigma": kanal.get("konum_sigma"), "r2": kanal.get("r2")} if kanal else None,
                  "gecersizleme_spot": {k: (v or {}).get("fiyat_spot") for k, v in ((trend or {}).get("gecersizleme") or {}).items()}},
        "taban_koni_80": {k: {"p10": v["p10"], "p90": v["p90"]} for k, v in ((cone or {}).get("ufuklar") or {}).items()},
        "tazelik": {"spot_yas_gun": ((fresh or {}).get("fiyat") or {}).get("spot_lbma_pm", {}).get("yas_gun"), "uyarilar": (fresh or {}).get("uyarilar")},
        "makro_son": snap.get("makro_son"),
    }


BOLUM_IDS = ["giris", "neden", "masa", "seviyeler", "buyuk_resim", "takvim", "kapanis"]
# Sekizinci bölüm (2026-09-16): yorumcu gözcüsü kayıt verdiyse "Piyasa ne diyor", büyük resim ile takvim arasında.
# Tek cümle büyük resmin içinde kayboluyordu (kullanıcı canlıda fark etmedi); kendi başlığıyla görünür olsun.
OPSIYONEL_BOLUM = "sesler"
BOLUM_SIRA = BOLUM_IDS[:5] + [OPSIYONEL_BOLUM] + BOLUM_IDS[5:]
# Kelime bütçesi alt sınırları (anchor.md tablosu); bölüm bunun %70'inin altında kalırsa düzeltme turu ister.
# Ölçüldü (2026-09-15): bütçesiz ilk sürüm 311 kelime, bütçeli ilk tur 302; model JSON kipinde kısa yazmaya eğilimli.
BOLUM_MIN = {"giris": 40, "neden": 90, "masa": 60, "seviyeler": 50, "buyuk_resim": 50, "sesler": 30, "takvim": 30, "kapanis": 30}
BUTCE_TOLERANS = 0.7


def budget_problems(bolumler: list[dict]) -> list[str]:
    kisa = [f"{b['id']} {len(str(b.get('metin', '')).split())} kelime (en az {BOLUM_MIN[b['id']]})" for b in bolumler
            if b.get("id") in BOLUM_MIN and len(str(b.get("metin", "")).split()) < BOLUM_MIN[b["id"]] * BUTCE_TOLERANS]
    return [f"bölümler bütçenin çok altında: {', '.join(kisa)}; bütçeye uygun uzunlukta yeniden yaz"] if kisa else []
BOLUM_BASLIK = {"giris": "Bugün ne oldu", "neden": "Neden düştü / yükseldi", "masa": "Masa nasıl okuyor", "seviyeler": "Hangi fiyatlar önemli", "buyuk_resim": "Büyük resim", "sesler": "Piyasa ne diyor", "takvim": "Bu hafta ne var", "kapanis": "Kapanış"}


def section_problems(bolumler: list[dict], wants_sesler: bool) -> list[str]:
    """`sesler` bölümü yalnız brifte `piyasa_sesleri` doluysa yazılır; eksikse ya da fazlaysa düzeltme turu ister."""
    has = any(b.get("id") == OPSIYONEL_BOLUM for b in bolumler)
    if wants_sesler and not has:
        return ["brifte piyasa_sesleri dolu: 'sesler' (Piyasa ne diyor) bölümü eksik; buyuk_resim ile takvim arasına 30–45 kelimelik bu bölümü ekle"]
    if not wants_sesler and has:
        return ["yorumcu kaydı yokken 'sesler' bölümü yazılmış; bu bölümü kaldır ve yorumculardan söz etme"]
    return []


def _normalize_anchor_output(sj: dict) -> dict:
    """Şema zorlaması olmayan sağlayıcılarda anahtar adları kayabilir; eş adları toparlar, eksikleri bildirir."""
    out = {"baslik": str(sj.get("baslik") or sj.get("title") or ""), "manset": str(sj.get("manset") or sj.get("manşet") or sj.get("headline") or ""), "ozet": str(sj.get("ozet") or sj.get("özet") or sj.get("summary") or "")}
    ham = sj.get("bolumler") or sj.get("bölümler") or sj.get("sections") or []
    if isinstance(ham, dict):
        ham = [{"id": k, **(v if isinstance(v, dict) else {"metin": v})} for k, v in ham.items()]
    bol = []
    for i, b in enumerate(ham):
        if not isinstance(b, dict):
            b = {"metin": str(b)}
        bid = str(b.get("id") or (BOLUM_IDS[i] if i < len(BOLUM_IDS) else f"b{i}"))
        metin = b.get("metin") or b.get("icerik") or b.get("içerik") or b.get("text") or b.get("paragraf") or b.get("content") or ""
        bol.append({"id": bid, "baslik": str(b.get("baslik") or b.get("başlık") or b.get("title") or BOLUM_BASLIK.get(bid, bid)), "metin": str(metin)})
    ids = [b["id"] for b in bol]
    eksik = [b["id"] for b in bol if not b["metin"].strip()]
    eksik_zorunlu = [i for i in BOLUM_IDS if i not in ids]
    fazla = [i for i in ids if i not in BOLUM_SIRA]
    if eksik or eksik_zorunlu or fazla or len(ids) != len(set(ids)):
        raise ValueError(f"bölüm yapısı hatalı: {len(bol)} bölüm, boş: {eksik}, eksik: {eksik_zorunlu}, tanımsız: {fazla}")
    out["bolumler"] = sorted(bol, key=lambda b: BOLUM_SIRA.index(b["id"]))   # yedi zorunlu + isteğe bağlı 'sesler', sabit sıra
    return out


def _int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _save(name: str, text: str) -> None:
    (LATEST_DIR / name).write_text(text)


def _short_headlines(hs: list[dict], n: int = 8) -> list[dict]:
    return [{"baslik": h["baslik"][:140], "kaynak": h["kaynak"], "saat_turkiye": turkiye_saati(h.get("zaman_utc")) or h.get("zaman_utc")} for h in hs[:n]]


def prepare_inputs() -> dict:
    """Bir turun paylaşılan girdileri: paket (betik + piyasa girdileri) ve başlıklar. Planlayıcı da bunu okur."""
    package = base_package()
    package.update(market_inputs.collect_market_inputs())
    # Yorumcu gözcüsü ayrı döngüde tazeler; burada yalnız disk okunur (24 saatten eski özet masaya gitmez).
    return {"package": package, "headlines": market_inputs.fetch_headlines(),
            "commentators": commentator_service.for_desk(commentator_service.read_digest())}


def _truncate(s: str | None, n: int = 1800) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + " …[kırpıldı]"



def run_full_pipeline(llm: LlmSettings, log=print, prepared: dict | None = None) -> dict:
    usage: dict[str, dict] = {}
    prepared = prepared or prepare_inputs()
    package, headlines = prepared["package"], prepared["headlines"]
    commentators = prepared.get("commentators") or []
    inputs = {k: package.get(k) for k in ("faiz_beklentisi", "enflasyon", "takvim", "pozisyon")}
    log(f"girdiler: faiz {(inputs['faiz_beklentisi'] or {}).get('toplanti_ayi_kontrati')}, pozisyon {(inputs['pozisyon'] or {}).get('net_uzun')}, takvim {len((inputs['takvim'] or {}).get('olaylar', []))} olay, haber {len(headlines)}")
    pause = lambda: time.sleep(llm.pause_seconds) if llm.pause_seconds else None  # noqa: E731

    # 1) Teknik analist → not-teknik.md (paket + gösterge sözlüğü)
    text, used, model = ask(llm, "technical_analyst", role_prompt("technical_analyst"), "Girdi paketi (JSON):\n" + json.dumps({**package, "sozluk": SOZLUK}, ensure_ascii=False) + "\n\nRol tanımındaki altı başlıkla notunu Markdown olarak yaz; en fazla 300 kelime, tablo yok.")
    pause()
    _save("not-teknik.md", text); usage["technical_analyst"] = {**used.as_dict(), "model": model}; log(f"technical ok {model} {used.as_dict()}")

    # 2) Takvim ve haber gözcüsü → not-takvim.json (yapılandırılmış; baş analist küçük girdi okur)
    text, used, model = ask(llm, "calendar_news_scout", role_prompt("calendar_news_scout"), "Son 24 saatin haber başlıkları:\n" + json.dumps(_short_headlines(headlines, 10), ensure_ascii=False) + "\n\nResmi olay takvimi (betik):\n" + json.dumps(package["takvim"], ensure_ascii=False) + "\n\nCanlı fiyat bloğu:\n" + json.dumps({"canli": package["canli"], "saat_turkiye": package.get("saat_turkiye"), "resmi_fiks": package["resmi_fiks"]}, ensure_ascii=False) + "\n\nRol tanımındaki JSON'u döndür.", TAKVIM_SCHEMA)
    pause()
    takvim = parse_json(text)
    _save("not-takvim.json", json.dumps(takvim, ensure_ascii=False, indent=2))
    _save("not-takvim.md", "# Takvim ve haber\n\n" + "\n".join(f"- {o.get('tarih')} {o.get('saat_turkiye')}: {o.get('olay')} — {o.get('onem')}" for o in takvim.get("takvim", [])) + "\n\n" + "\n".join(f"- {h.get('baslik')} ({h.get('kaynak')}) {h.get('iddia') or ''}".rstrip() for h in takvim.get("haberler", [])) + f"\n\n{takvim.get('surpriz') or ''}\n{takvim.get('bugun_cumle') or ''}")
    usage["calendar_news_scout"] = {**used.as_dict(), "model": model}; log(f"calendar ok {model}")

    # 3) Makro analist → makro-skor-karti.json + not-makro.md
    macro = macro_changes()
    text, used, model = ask(llm, "macro_analyst", role_prompt("macro_analyst"), "Makro seriler (son değer, 5 ve 20 gözlemlik değişim; piyasa serileri yüzde):\n" + json.dumps(macro, ensure_ascii=False) + "\n\nFaiz beklentisi (vadeli işlemlerden, betik):\n" + json.dumps(package["faiz_beklentisi"], ensure_ascii=False) + "\n\nEnflasyon (betik):\n" + json.dumps(package["enflasyon"], ensure_ascii=False) + "\n\nPozisyon (betik):\n" + json.dumps(package["pozisyon"], ensure_ascii=False) + "\n\nTakvim (gözcü):\n" + json.dumps(takvim.get("takvim"), ensure_ascii=False) + "\n\nCanlı fiyat ve tazelik:\n" + json.dumps({"canli": package["canli"], "saat_turkiye": package.get("saat_turkiye"), "resmi_fiks": package["resmi_fiks"], "tazelik": package["tazelik"]}, ensure_ascii=False) + "\n\nHaber başlıkları (gözcü):\n" + json.dumps(takvim.get("haberler"), ensure_ascii=False) + "\n\nRol tanımındaki JSON'u döndür.", MAKRO_SCHEMA)
    pause()
    macro_card = parse_json(text); macro_card["as_of"] = package["as_of"]
    _save("makro-skor-karti.json", json.dumps(macro_card, ensure_ascii=False, indent=2))
    macro_note = f"# Makro not — {package['as_of']}\n\n**Piyasa neyi fiyatlıyor:** {macro_card['piyasa_anlatisi']['ozet']}\n\n**Masanın görüşü:** {macro_card['piyasa_anlatisi']['masanin_gorusu']}\n\n" + "\n".join(f"- {s['surucu']}: {s['altin_icin']} ({_int(s.get('guc')):+d}) — {s['kanit']}" for s in macro_card["suruculer"])
    _save("not-makro.md", macro_note); usage["macro_analyst"] = {**used.as_dict(), "model": model}; log(f"macro ok {model}")

    # 4) Baş analist → brif.json (teknik not kırpık, takvim JSON, makro kart)
    text, used, model = ask(llm, "chief_analyst", role_prompt("chief_analyst"), "Betik paketi:\n" + json.dumps(package, ensure_ascii=False) + "\n\n--- teknik not ---\n" + _truncate(_md("not-teknik.md"), 1400) + "\n\n--- takvim ve haber (JSON) ---\n" + json.dumps(takvim, ensure_ascii=False) + "\n\n--- makro skor kartı ---\n" + json.dumps({k: macro_card.get(k) for k in ("piyasa_anlatisi", "suruculer")}, ensure_ascii=False) + "\n\n--- yorumcular (gözcü; haber başlıklarından, son " + str(settings.commentator_window_hours) + " saat; adsız, sayısal hedefler bilerek verilmedi) ---\n" + (json.dumps({"ozet": commentator_service.desk_summary(commentators, len(commentator_service.load_commentators())), "kayitlar": commentators}, ensure_ascii=False) if commentators else "veri yok") + "\n\nBrifi JSON olarak döndür (şemadaki alanlar; rol tanımındaki sınırlar). Şu an = canlı blok; seviyeler canlıya göre.", BRIF_SCHEMA)
    brief = parse_json(text); brief["as_of"] = package["as_of"]; brief["yazildi_utc"] = package.get("simdi_utc")
    _save("brif.json", json.dumps(brief, ensure_ascii=False, indent=2)); usage["chief_analyst"] = {**used.as_dict(), "model": model}; log(f"chief ok {model}")

    result = write_anchor_text(llm, package, brief, headlines, usage, log, commentators=commentators)
    result["run_mode"] = "full"
    return result


def write_anchor_text(llm: LlmSettings, package: dict, brief: dict, headlines: list, usage: dict, log=print, commentators: list | None = None) -> dict:
    """Son alıcı metni: yedi bölüm, yorumcu kaydı varsa sekiz; sayı/jargon denetiminden geçmezse tek düzeltme turu, yine geçmezse hata.
    `commentators`: yorumcu gözcüsünün bugünkü kayıtları; metinde izleme listesindeki bir ad geçiyorsa kaydı olmalı."""
    configured_names = [p["ad"] for p in commentator_service.load_commentators()]
    attribution = lambda metin: commentator_service.attribution_problems(metin, commentators or [], configured_names)  # noqa: E731
    # Yorumcu cümlesindeki sayı anlatıcıya gitmez ve denetim havuzuna girmez; aksi hâlde baş analistin
    # yorumcudan aktardığı hedef "girdideki sayı" sayılır ve metne sızardı.
    brief = {**brief, "piyasa_sesleri": commentator_service.strip_numbers(str(brief.get("piyasa_sesleri") or ""))}
    wants_sesler = bool(brief["piyasa_sesleri"].strip())
    sections_note = ("sekiz bölüm: yedi standart bölüm artı 'sesler' / Piyasa ne diyor, buyuk_resim ile takvim arasında, 30–45 kelime" if wants_sesler
                     else "yedi bölüm; yorumcu kaydı yok, 'sesler' bölümü yazma")
    audit_package = {"brif": brief, "betik": {k: package.get(k) for k in ("canli", "canli_zaman_utc", "saat_turkiye", "resmi_fiks", "seviyeler_canli", "momentum", "hizalanma", "trend", "vadeli", "faiz_beklentisi", "enflasyon", "takvim", "pozisyon")}, "haberler": _short_headlines(headlines, 4)}
    brief_note = ""
    if brief.get("yazildi_utc") and package.get("simdi_utc"):
        try:
            age_min = int((dt.datetime.fromisoformat(package["simdi_utc"]) - dt.datetime.fromisoformat(brief["yazildi_utc"])).total_seconds() // 60)
            if age_min >= 20:
                brief_note = f" Brif {age_min} dakika önce yazıldı; içindeki fiyatlar eski olabilir, şu anki fiyat yalnız betik bloğundaki canli.fiyat."
        except ValueError:
            pass
    user = "Brif (masanın tezi):" + brief_note + "\n" + json.dumps(audit_package["brif"], ensure_ascii=False) + "\n\nBetik çıktıları:\n" + json.dumps(audit_package["betik"], ensure_ascii=False) + "\n\nHaber başlıkları:\n" + json.dumps(audit_package["haberler"], ensure_ascii=False) + "\n\nSon alıcı metnini JSON olarak yaz: baslik, manset, ozet, bolumler (" + sections_note + "; sayılar rakamla, manşet ve özet dahil)."
    live_price = (package.get("canli") or {}).get("fiyat")
    text, used, model = ask(llm, "anchor", role_prompt("anchor"), user, SUNUM_SCHEMA)
    _save("anchor-raw.txt", text)
    def drop_stray_sesler(out: dict) -> dict:
        # Brif yorumcu kaydı vermediyse anlatıcının yine de yazdığı 'sesler' bölümü dayanaksızdır: turu düşürmek yerine
        # bölüm atılır (şema zorlamayan sağlayıcı ve sahte sağlayıcı her bölümü üretir).
        if not wants_sesler and any(b["id"] == OPSIYONEL_BOLUM for b in out["bolumler"]):
            log("anchor: brif yorumcu kaydı vermedi, 'sesler' bölümü atıldı")
            out["bolumler"] = [b for b in out["bolumler"] if b["id"] != OPSIYONEL_BOLUM]
        return out

    try:
        output = drop_stray_sesler(_normalize_anchor_output(parse_json(text)))
        structure_problems = []
    except ValueError as error:
        output = parse_json(text); structure_problems = [str(error) + " — her bölüm için 'id', 'baslik', 'metin' anahtarlarını kullan"]
    flat = " ".join([str(output.get("baslik", "")), str(output.get("manset", "")), str(output.get("ozet", ""))] + [str(b.get("metin", "")) for b in (output.get("bolumler") or []) if isinstance(b, dict)])
    problems = structure_problems + audit_text(flat, audit_package, live_price=live_price) + attribution(flat) + (budget_problems(output.get("bolumler") or []) + section_problems(output.get("bolumler") or [], wants_sesler) if not structure_problems else [])
    total = used
    if problems:
        log(f"anchor denetim: {problems}; düzeltme isteniyor")
        text2, used2, _ = ask(llm, "anchor", role_prompt("anchor"), user + "\n\nÖNCEKİ DENEMENDE ŞU KURAL İHLALLERİ VARDI, DÜZELTEREK YENİDEN YAZ:\n- " + "\n- ".join(problems) + "\n\nÖnceki metin:\n" + json.dumps(output, ensure_ascii=False), SUNUM_SCHEMA)
        _save("anchor-raw-2.txt", text2)
        output = drop_stray_sesler(_normalize_anchor_output(parse_json(text2)))
        total = used + used2
        flat = " ".join([output["baslik"], output["manset"], output["ozet"]] + [b["metin"] for b in output["bolumler"]])
        problems = audit_text(flat, audit_package, live_price=live_price) + attribution(flat) + section_problems(output["bolumler"], wants_sesler)
        if problems:
            raise RuntimeError(f"anchor metni denetimi geçemedi: {problems}")
    usage["anchor"] = {**total.as_dict(), "model": model}; log(f"anchor ok {model}")
    local_time = ""
    if package.get("canli_zaman_utc"):
        local_time = dt.datetime.fromisoformat(package["canli_zaman_utc"]).astimezone(dt.timezone(dt.timedelta(hours=3))).strftime("%H:%M")
    result = {"as_of": package["as_of"], "local_time": local_time, "title": output["baslik"], "headline": output["manset"], "summary": output["ozet"],
              "sections": [{"id": b["id"], "title": b["baslik"], "text": b["metin"]} for b in output["bolumler"]], "usage": usage}
    _save("commentary.json", json.dumps(result, ensure_ascii=False, indent=2))
    _save("commentary.md", f"# {result['title']}\n\n**{result['headline']}**\n\n{result['summary']}\n\n" + "".join(f"## {s['title']}\n\n{s['text']}\n\n" for s in result["sections"]))
    return result


def run_fast_pipeline(llm: LlmSettings, log=print, prepared: dict | None = None) -> dict:
    prepared = prepared or prepare_inputs()
    package, headlines = prepared["package"], prepared["headlines"]
    brief = _j("brif.json") or {"tez": "Masanın son derin analizi yok; yalnız betik çıktılarıyla anlat, yön verme.", "yon": "belirsiz", "guven": "dusuk"}
    result = write_anchor_text(llm, package, brief, headlines, {}, log, commentators=prepared.get("commentators") or [])
    result["run_mode"] = "fast"
    return result
