"""Yorumun sesli anlatımı: metin üretildikten sonra **bir kez** Gemini konuşma modeliyle
seslendirilir, MP3 olarak sürüm klasörüne yazılır; API dosyayı diskten verir.

Neden sunucuda: tarayıcı sentezleyicisi Türkçede vurgu ve ritim veremiyor (kullanıcı
bildirimi, 2026-09-15). Ölçüldü: 394 karakter → 33 sn ses, 17 sn üretim (3.1 flash, Kore).
Tam metin ~2.000 karakter ≈ 2,5 dk ses. Tek istek: bölüm bölüm istemek prosodiyi bozuyor
ve ücretsiz katman istek sınırına takılıyor; bölüm zamanları karakter oranıyla **tahmin**
edilir ve `estimated: true` ile işaretlenir.

Ham ses 24 kHz 16 bit PCM (2,9 MB/dk); mobil için `lameenc` ile 48 kbps mono MP3'e
sıkıştırılır (~0,36 MB/dk). ffmpeg imajda yok, bu yüzden saf kütüphane.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

NARRATION_FILE = "commentary.mp3"
NARRATION_LEDGER = "narration_runs.csv"


class QuotaExhausted(RuntimeError):
    """Sağlayıcı 429 verdi ve denemeler bitti: çağıran soğuma süresine girer."""
NARRATION_META = "narration.json"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
STYLE = ("Sen sakin ve güven veren bir finans haber anlatıcısısın. Aşağıdaki Türkçe metni doğal konuşma "
         "ritmiyle, cümle sonlarında kısa duraklarla, sayıları Türkçe okuyarak, abartısız vurgularla seslendir. "
         "Metne hiçbir şey ekleme, yalnız oku:\n\n")
STYLE_VERSION = "narrator-v1"


def narration_segments(item: dict) -> list[dict]:
    """Okunacak metnin parçaları ve karakter aralıkları: manşet, özet, bölümler (başlık + metin)."""
    parts = [("headline", item.get("headline", "")), ("summary", item.get("summary", ""))]
    parts += [(s["id"], f"{s['title']}. {s['text']}") for s in item.get("sections", [])]
    segments, cursor = [], 0
    for key, text in parts:
        text = (text or "").strip()
        if not text:
            continue
        segments.append({"id": key, "text": text, "start_char": cursor, "end_char": cursor + len(text)})
        cursor += len(text) + 2  # "\n\n" ayracı
    return segments


def narration_text(segments: list[dict]) -> str:
    return "\n\n".join(s["text"] for s in segments)


def estimate_times(segments: list[dict], duration: float) -> list[dict]:
    """Karakter payıyla orantılı zaman aralıkları (saniye); toplam süre ses dosyasından."""
    total = max(1, segments[-1]["end_char"]) if segments else 1
    out = []
    for s in segments:
        out.append({"id": s["id"], "start": round(duration * s["start_char"] / total, 2), "end": round(duration * s["end_char"] / total, 2)})
    return out


def synthesize_pcm(text: str, *, api_key: str, model: str, voice: str, timeout: int = 180, attempts: int = 3) -> tuple[bytes, int]:
    """Gemini TTS → (16 bit mono PCM, örnekleme hızı). 429/503'te bekleyip yeniden dener."""
    body = {"contents": [{"parts": [{"text": STYLE + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    url = GEMINI_URL.format(model=model)
    last: Exception | None = None
    quota_hit = False
    for attempt in range(attempts):
        try:
            response = httpx.post(url, params={"key": api_key}, json=body, timeout=timeout)
            quota_hit = response.status_code == 429
            if response.status_code in (429, 503) and attempt < attempts - 1:
                wait = float(response.headers.get("retry-after") or 15 * (attempt + 1))
                log.warning("TTS %s; %.0f sn sonra yeniden", response.status_code, wait)
                time.sleep(min(wait, 90))
                continue
            response.raise_for_status()
            part = response.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
            mime = part.get("mimeType", "")
            rate = int(mime.split("rate=")[1].split(";")[0]) if "rate=" in mime else 24000
            return base64.b64decode(part["data"]), rate
        except (httpx.HTTPError, KeyError, ValueError) as error:
            last = error
            if attempt < attempts - 1:
                time.sleep(5)
    if quota_hit:
        raise QuotaExhausted(f"TTS kotası (429): {last}")
    raise RuntimeError(f"TTS üretilemedi: {last}")


def encode_mp3(pcm: bytes, rate: int, *, bitrate_kbps: int = 48) -> bytes:
    import lameenc  # ağır bağımlılık; yalnız üretimde yüklenir

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(bitrate_kbps)
    encoder.set_in_sample_rate(rate)
    encoder.set_channels(1)
    encoder.set_quality(2)
    return bytes(encoder.encode(pcm)) + bytes(encoder.flush())


def narrate(version_dir: Path, item: dict, *, api_key: str, model: str, voice: str, bitrate_kbps: int = 48) -> dict:
    """Sürüm klasörüne `commentary.mp3` + `narration.json` yazar, meta'yı döner."""
    segments = narration_segments(item)
    text = narration_text(segments)
    started = time.time()
    pcm, rate = synthesize_pcm(text, api_key=api_key, model=model, voice=voice)
    duration = len(pcm) / 2 / rate
    mp3 = encode_mp3(pcm, rate, bitrate_kbps=bitrate_kbps)
    tmp = version_dir / f".{NARRATION_FILE}.tmp"
    tmp.write_bytes(mp3)
    os.replace(tmp, version_dir / NARRATION_FILE)
    meta = {"voice": voice, "model": model, "style": STYLE_VERSION, "duration_seconds": round(duration, 2),
            "bitrate_kbps": bitrate_kbps, "bytes": len(mp3), "characters": len(text), "generation_seconds": round(time.time() - started, 1),
            "segments": estimate_times(segments, duration), "estimated": True}
    (version_dir / NARRATION_META).write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def append_ledger(ledger_dir: Path, version: str, ok: bool, seconds: float, size: int, error: str = "") -> None:
    """Her deneme (başarılı ya da değil) kota harcar; bütçe bu defterden sayılır."""
    import csv
    ledger_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_dir / NARRATION_LEDGER
    new = not path.exists()
    with open(path, "a", newline="") as handle:
        writer = csv.writer(handle)
        if new:
            writer.writerow(["attempted_at", "version", "ok", "seconds", "bytes", "error"])
        writer.writerow([time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), version, int(ok), round(seconds, 1), size, error[:200]])


def read_ledger(ledger_dir: Path) -> list[dict]:
    import csv
    path = ledger_dir / NARRATION_LEDGER
    if not path.exists():
        return []
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def read_meta(version_dir: Path) -> dict | None:
    path = version_dir / NARRATION_META
    if not path.exists() or not (version_dir / NARRATION_FILE).exists():
        return None
    try:
        return json.loads(path.read_text())
    except ValueError:
        return None
