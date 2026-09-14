"""Çıktı denetimi (betik): metindeki sayılar girdi paketinde var mı, yasak terim geçiyor mu.

Zayıf modeller sayı uydurabilir ve piyasa jargonu kullanabilir; bu denetim reddeder ve düzeltme ister.
"""
from __future__ import annotations

import re

YASAK = ["ATR", "SMA", "EMA", "RSI", "MACD", "ADX", "VIX", "DXY", "Dow", "FOMC", "Fed ", "Fed'", "Fed,", "TIPS", "COT", "GVZ", "PAXG", "GC=F", "LBMA"]
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


def audit_text(metin: str, paket) -> list[str]:
    havuz = girdi_sayilari(paket)
    sorunlar = []
    yabanci = sorted({m for m in SAYI_RX.findall(metin) if (v := _to_float(m)) is not None and not _eslesir(v, havuz)})
    if yabanci:
        sorunlar.append("girdide olmayan sayılar: " + ", ".join(yabanci))
    yasak = [y for y in YASAK if y in metin]
    if yasak:
        sorunlar.append("yasak terimler: " + ", ".join(y.strip(" ',") for y in yasak))
    if re.search(r"\b(bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz|on|yüz|bin)\s+nokta\s+", metin):
        sorunlar.append("sayılar sözcükle ve 'nokta' ile yazılmış; rakamla ve virgülle yazılmalı")
    return sorunlar
