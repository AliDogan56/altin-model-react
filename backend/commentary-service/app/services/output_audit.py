"""Çıktı denetimi (betik): metindeki sayılar girdi paketinde var mı, yasak terim geçiyor mu.

Zayıf modeller sayı uydurabilir ve piyasa jargonu kullanabilir; bu denetim reddeder ve düzeltme ister.
"""
from __future__ import annotations

import re

YASAK = ["ATR", "SMA", "EMA", "RSI", "MACD", "ADX", "VIX", "DXY", "Dow", "FOMC", "Fed", "TIPS", "COT", "GVZ", "PAXG", "LBMA"]
# Tam kelime: "Dowding" ya da "FedWatch" içindeki parça yakalanmaz; "Fed'in", "Fed." yakalanır (ölçüldü: "Dow" alt dizesi
# bir turda gereksiz düzeltme çağrısı yedi). GC=F ayrı: "=" kelime sınırı vermez.
YASAK_RX = re.compile(r"\b(" + "|".join(re.escape(y) for y in YASAK) + r")\b|GC=F")
SAYI_RX = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def _to_float(s: str) -> float | None:
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def girdi_sayilari(obj) -> set[float]:
    out: set[float] = set()
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, str):
        for m in SAYI_RX.findall(obj):
            v = _to_float(m)
            if v is not None:
                out.add(v)
        for m in re.findall(r"\d+\.\d+", obj):  # İngilizce ondalık (4286.23)
            out.add(float(m))
    elif isinstance(obj, dict):
        for v in obj.values():
            out |= girdi_sayilari(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out |= girdi_sayilari(v)
    return out


def _eslesir(v: float, havuz: set[float]) -> bool:
    if v <= 31 or 2020 <= v <= 2030 or v in (50, 52, 100, 200, 250):
        return True  # sayım, gün, saat, yıl, ortalama pencereleri
    for h in havuz:
        if h == 0:
            continue
        if abs(v - h) <= 0.06 or abs(v / h - 1) <= 0.006:  # yuvarlama payı
            return True
        if abs(v - round(h)) < 1e-9 or abs(v - round(h, 1)) < 1e-9:
            return True
    return False


def _tr(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _canli_gecer(metin: str, fiyat: float) -> bool:
    """Canlı fiyat metinde geçiyor mu: tam, bir ondalık ya da tam sayıya yuvarlanmış biçim (Türkçe ayraçlarla)."""
    adaylar = {_tr(fiyat), _tr(round(fiyat, 1)).rstrip("0").rstrip(","), f"{round(fiyat):,}".replace(",", ".")}
    return any(a and a in metin for a in adaylar)


def audit_text(metin: str, paket, live_price: float | None = None) -> list[str]:
    havuz = girdi_sayilari(paket)
    sorunlar = []
    yabanci = sorted({m for m in SAYI_RX.findall(metin) if (v := _to_float(m)) is not None and not _eslesir(v, havuz)})
    if yabanci:
        sorunlar.append("girdide olmayan sayılar: " + ", ".join(yabanci))
    yasak = sorted({m.group(0) for m in YASAK_RX.finditer(metin)})
    if yasak:
        sorunlar.append("yasak terimler: " + ", ".join(yasak))
    if live_price and yabanci == [] and SAYI_RX.search(metin) and not _canli_gecer(metin, live_price):
        sorunlar.append(f"şu anki fiyat metinde yok: canlı fiyat {_tr(live_price)} dolar girişte ve manşette geçmeli")
    if re.search(r"\b(bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz|on|yüz|bin)\s+nokta\s+", metin):
        sorunlar.append("sayılar sözcükle ve 'nokta' ile yazılmış; rakamla ve virgülle yazılmalı")
    return sorunlar
