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

from ..market_constants import LATEST_DIR, MACRO_CSV, MARKET_CSV, PROMPTS_DIR
from . import market_inputs_service as market_inputs
from .llm_config import LlmSettings
from .llm_gateway import TokenUsage, ask, parse_json
from .output_audit import audit_text

NO_TOOLS_NOTE = """

## Bu ortamda araç yok
Dosya okuma, betik çalıştırma ve web araması yapamazsın. Bütün girdiler aşağıdaki pakette hazır verilir.

## Sayı ve dil kuralları (denetlenir)
- Yalnız pakette geçen sayıları kullan; yuvarlayabilirsin (4295 → 4.295; 2,28 → 2,3). Pakette olmayan olasılık, oran, tarih
  ya da fiyat yazma. Örneğin pakette faiz artışı olasılığı yoksa olasılık cümlesi kurma.
- Sayılar rakamla ve Türkçe biçimde: "4.295 dolar", "yüzde 2,3". Sayıyı sözcükle ("iki nokta sıfır sekiz") yazma.
- Yasak kısaltma ve jargon: ATR, SMA, EMA, RSI, MACD, ADX, VIX, DXY, Dow, FOMC, Fed, TIPS, COT, GVZ, PAXG, LBMA.
  Bunların yerine sade karşılık: "günlük olağan dalgalanma", "son 50 günün ortalaması", "borsadaki korku ölçüsü",
  "dolar endeksi", "zirveler ve dipler", "Amerikan Merkez Bankası'nın faiz toplantısı", "reel faiz", "Londra resmi fiksi".
- Bir seviye fiyatın altına düştüyse o seviye "kırılan destek"tir ve artık üstte tavan olur; ters yazma.
- Reel faiz ve dolar yükselişi altın için aleyhtedir; düşüşü lehtedir. Yönü ters yazma.
- Yön iddiası yok; masa yön vermiyorsa bunu söyle.
- Rol tanımındaki cümleleri metne kopyalama ("Sen ... spikerisin" gibi); kendinden "masa" diye söz et, "ben" deme.
- Saatleri Türkiye saatiyle ver (paketteki `saat_turkiye`); UTC yazma.
- Faiz artışı olasılığı paketteki `faiz_beklentisi` bloğundan gelir ve "vadeli işlem fiyatlarından türetilen olasılık" diye anılır; haber kaynağına bağlanmaz."""

SUNUM_SCHEMA = {
    "type": "object",
    "properties": {
        "baslik": {"type": "string"}, "manset": {"type": "string"}, "ozet": {"type": "string"},
        "bolumler": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string", "enum": ["giris", "neden", "masa", "seviyeler", "buyuk_resim", "takvim", "kapanis"]},
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
    },
    "required": ["baslik", "tez", "yon", "guven", "ana_noktalar", "riskler", "celiskiler", "veri_uyarilari", "takvim_one_cikan", "bugun", "piyasa_anlatisi"], "additionalProperties": False,
}



SKIPPED_SECTIONS = ("Girdiler", "Çıktılar", "Adımlar", "Durum", "Hedef arayüz", "Eşleme")


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


def base_package() -> dict:
    snap, lv, mom, trend, cone, fresh = (_j(n) for n in ("snapshot.json", "levels.json", "momentum.json", "trend.json", "base_cone.json", "freshness.json"))
    if not snap or not lv:
        raise RuntimeError("snapshot/levels yok: önce snapshot_service.build_snapshot çalışmalı")
    canli = lv.get("canli") or {}
    slim = lambda xs: [{"spot_esdeger": x["spot_esdeger"], "kaynak_sayisi": x["kaynak_sayisi"], "uzaklik_pct": x.get("canli_uzaklik_pct", x.get("uzaklik_pct"))} for x in xs[:3]]  # noqa: E731
    tl = (trend or {}).get("trend_cizgileri") or {}
    cizgi = lambda ln: None if not ln else {"bugun_spot": ln.get("bugunku_deger_spot"), "temas": ln.get("temas"), "kirildi": ln.get("kirildi")}  # noqa: E731
    kanal = ((trend or {}).get("regresyon_kanali") or {}).get("250")
    return {
        "as_of": snap["as_of"], "simdi_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "canli": snap.get("canli"), "canli_zaman_utc": snap.get("canli_zaman_utc"), "basis": snap.get("basis"),
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
BOLUM_BASLIK = {"giris": "Bugün ne oldu", "neden": "Neden düştü / yükseldi", "masa": "Masa nasıl okuyor", "seviyeler": "Hangi fiyatlar önemli", "buyuk_resim": "Büyük resim", "takvim": "Bu hafta ne var", "kapanis": "Kapanış"}


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
    out["bolumler"] = bol
    eksik = [b["id"] for b in bol if not b["metin"].strip()]
    if len(bol) != 7 or eksik:
        raise ValueError(f"bölüm yapısı hatalı: {len(bol)} bölüm, boş: {eksik}")
    return out


def _int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _save(name: str, text: str) -> None:
    (LATEST_DIR / name).write_text(text)


def _short_headlines(hs: list[dict], n: int = 8) -> list[dict]:
    return [{"baslik": h["baslik"][:140], "kaynak": h["kaynak"], "zaman_utc": h["zaman_utc"]} for h in hs[:n]]


def _truncate(s: str | None, n: int = 1800) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + " …[kırpıldı]"



def run_full_pipeline(llm: LlmSettings, log=print) -> dict:
    usage: dict[str, dict] = {}
    package = base_package()
    inputs = market_inputs.collect_market_inputs()
    package.update(inputs)
    headlines = market_inputs.fetch_headlines()
    log(f"girdiler: faiz {inputs['faiz_beklentisi'].get('toplanti_ayi_kontrati')}, pozisyon {inputs['pozisyon'].get('net_uzun')}, takvim {len(inputs['takvim'].get('olaylar', []))} olay, haber {len(headlines)}")
    pause = lambda: time.sleep(llm.pause_seconds) if llm.pause_seconds else None  # noqa: E731

    # 1) Teknik analist → not-teknik.md
    text, used, model = ask(llm, "technical_analyst", role_prompt("technical_analyst"), "Girdi paketi (JSON):\n" + json.dumps(package, ensure_ascii=False) + "\n\nRol tanımındaki altı başlıkla notunu Markdown olarak yaz; en fazla 300 kelime, tablo yerine kısa maddeler.")
    pause()
    _save("not-teknik.md", text); usage["technical_analyst"] = {**used.as_dict(), "model": model}; log(f"technical ok {model} {used.as_dict()}")

    # 2) Takvim ve haber gözcüsü → not-takvim.md (RSS başlıklarıyla)
    text, used, model = ask(llm, "calendar_news_scout", role_prompt("calendar_news_scout"), "Son 24 saatin haber başlıkları (RSS, kaynak ve saatiyle):\n" + json.dumps(headlines, ensure_ascii=False) + "\n\nResmi olay takvimi (betik):\n" + json.dumps(package["takvim"], ensure_ascii=False) + "\n\nCanlı fiyat bloğu:\n" + json.dumps({"canli": package["canli"], "resmi_fiks": package["resmi_fiks"]}, ensure_ascii=False) + "\n\nRol tanımındaki dört başlıkla notunu yaz; en fazla 250 kelime. Takvimde olmayan olay uydurma; başlıkların ötesinde içerik uydurma.")
    pause()
    _save("not-takvim.md", text); usage["calendar_news_scout"] = {**used.as_dict(), "model": model}; log(f"calendar ok {model}")

    # 3) Makro analist → makro-skor-karti.json + not-makro.md
    macro = macro_changes()
    text, used, model = ask(llm, "macro_analyst", role_prompt("macro_analyst"), "Makro seriler (son değer, 5 ve 20 gözlemlik değişim; piyasa serileri yüzde):\n" + json.dumps(macro, ensure_ascii=False) + "\n\nFaiz beklentisi (vadeli işlemlerden, betik):\n" + json.dumps(package["faiz_beklentisi"], ensure_ascii=False) + "\n\nEnflasyon (betik):\n" + json.dumps(package["enflasyon"], ensure_ascii=False) + "\n\nPozisyon (CFTC, betik):\n" + json.dumps(package["pozisyon"], ensure_ascii=False) + "\n\nTakvim:\n" + json.dumps(package["takvim"], ensure_ascii=False) + "\n\nCanlı fiyat ve tazelik:\n" + json.dumps({"canli": package["canli"], "resmi_fiks": package["resmi_fiks"], "tazelik": package["tazelik"]}, ensure_ascii=False) + "\n\nHaber başlıkları:\n" + json.dumps(headlines, ensure_ascii=False) + "\n\nGünlük kısa mod: JSON döndür (piyasa_anlatisi: ozet ve masanin_gorusu, her biri en fazla 80 kelime; suruculer: en az altı sürücü, kanit tek cümle).", MAKRO_SCHEMA)
    pause()
    macro_card = parse_json(text); macro_card["as_of"] = package["as_of"]
    _save("makro-skor-karti.json", json.dumps(macro_card, ensure_ascii=False, indent=2))
    macro_note = f"# Makro not — {package['as_of']}\n\n**Piyasa neyi fiyatlıyor:** {macro_card['piyasa_anlatisi']['ozet']}\n\n**Masanın görüşü:** {macro_card['piyasa_anlatisi']['masanin_gorusu']}\n\n" + "\n".join(f"- {s['surucu']}: {s['altin_icin']} ({_int(s.get('guc')):+d}) — {s['kanit']}" for s in macro_card["suruculer"])
    _save("not-makro.md", macro_note); usage["macro_analyst"] = {**used.as_dict(), "model": model}; log(f"macro ok {model}")

    # 4) Baş analist → brif.json
    text, used, model = ask(llm, "chief_analyst", role_prompt("chief_analyst"), "Betik çıktıları:\n" + json.dumps(package, ensure_ascii=False) + "\n\n--- not-teknik.md ---\n" + _truncate(_md("not-teknik.md")) + "\n\n--- not-takvim.md ---\n" + _truncate(_md("not-takvim.md")) + "\n\n--- makro-skor-karti.json ---\n" + json.dumps({k: macro_card.get(k) for k in ("piyasa_anlatisi", "suruculer")}, ensure_ascii=False) + "\n\nBrifi JSON olarak döndür (şemadaki alanlar; listeler en fazla 5 madde, tez en fazla 120 kelime). Şu an = canlı blok; seviyeler canlıya göre.", BRIF_SCHEMA)
    pause()
    brief = parse_json(text); brief["as_of"] = package["as_of"]
    _save("brif.json", json.dumps(brief, ensure_ascii=False, indent=2)); usage["chief_analyst"] = {**used.as_dict(), "model": model}; log(f"chief ok {model}")

    result = write_anchor_text(llm, package, brief, headlines, usage, log)
    result["run_mode"] = "full"
    return result


def write_anchor_text(llm: LlmSettings, package: dict, brief: dict, headlines: list, usage: dict, log=print) -> dict:
    """Son alıcı metni: yedi bölüm; sayı/jargon denetiminden geçmezse tek düzeltme turu, yine geçmezse hata."""
    audit_package = {"brif": brief, "betik": {k: package.get(k) for k in ("canli", "canli_zaman_utc", "resmi_fiks", "seviyeler_canli", "momentum", "hizalanma", "trend", "vadeli", "faiz_beklentisi", "enflasyon", "takvim", "pozisyon")}, "haberler": headlines[:6]}
    user = "Brif (masanın tezi):\n" + json.dumps(audit_package["brif"], ensure_ascii=False) + "\n\nBetik çıktıları:\n" + json.dumps(audit_package["betik"], ensure_ascii=False) + "\n\nHaber başlıkları:\n" + json.dumps(audit_package["haberler"], ensure_ascii=False) + "\n\nSon alıcı metnini JSON olarak yaz: baslik, manset, ozet, bolumler (yedi bölüm; sayılar rakamla, manşet ve özet dahil)."
    text, used, model = ask(llm, "anchor", role_prompt("anchor"), user, SUNUM_SCHEMA)
    _save("anchor-raw.txt", text)
    try:
        output = _normalize_anchor_output(parse_json(text))
        structure_problems = []
    except ValueError as error:
        output = parse_json(text); structure_problems = [str(error) + " — her bölüm için 'id', 'baslik', 'metin' anahtarlarını kullan"]
    flat = " ".join([str(output.get("baslik", "")), str(output.get("manset", "")), str(output.get("ozet", ""))] + [str(b.get("metin", "")) for b in (output.get("bolumler") or []) if isinstance(b, dict)])
    problems = structure_problems + audit_text(flat, audit_package)
    total = used
    if problems:
        log(f"anchor denetim: {problems}; düzeltme isteniyor")
        text2, used2, _ = ask(llm, "anchor", role_prompt("anchor"), user + "\n\nÖNCEKİ DENEMENDE ŞU KURAL İHLALLERİ VARDI, DÜZELTEREK YENİDEN YAZ:\n- " + "\n- ".join(problems) + "\n\nÖnceki metin:\n" + json.dumps(output, ensure_ascii=False), SUNUM_SCHEMA)
        _save("anchor-raw-2.txt", text2)
        output = _normalize_anchor_output(parse_json(text2))
        total = used + used2
        flat = " ".join([output["baslik"], output["manset"], output["ozet"]] + [b["metin"] for b in output["bolumler"]])
        problems = audit_text(flat, audit_package)
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


def run_fast_pipeline(llm: LlmSettings, log=print) -> dict:
    package = base_package()
    brief = _j("brif.json") or {"tez": "Masanın son derin analizi yok; yalnız betik çıktılarıyla anlat, yön verme.", "yon": "belirsiz", "guven": "dusuk"}
    package.update(market_inputs.collect_market_inputs())
    result = write_anchor_text(llm, package, brief, market_inputs.fetch_headlines(), {}, log)
    result["run_mode"] = "fast"
    return result
