"""Tek HTTP giriş noktası: FRED ve Yahoo TLS parmak izine bakar (curl_cffi ile taklit); kalanı httpx.
Ücretsiz uçlar 429/5xx döndürebilir: üstel bekleme ile yeniden deneme ve Yahoo için query1 → query2 yedeği."""
from __future__ import annotations

import time

import httpx

from ..market_constants import USER_AGENT

RETRY_STATUS = {429, 500, 502, 503, 504}


def _alternates(url: str) -> list[str]:
    urls = [url]
    if "query1.finance.yahoo.com" in url:
        urls.append(url.replace("query1.finance.yahoo.com", "query2.finance.yahoo.com"))
    return urls


def _get(url: str, timeout: int, attempts: int = 4) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(attempts):
        for candidate in _alternates(url):
            try:
                response = httpx.get(candidate, headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/csv,*/*"}, timeout=timeout, follow_redirects=True)
                if response.status_code in RETRY_STATUS:
                    last_error = RuntimeError(f"{response.status_code} for {candidate}")
                    continue
                response.raise_for_status()
                return response
            except httpx.HTTPError as error:
                last_error = error
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"{url}: {attempts} denemede alınamadı ({last_error})")


def _impersonated_json(url: str, timeout: int):
    try:
        from curl_cffi import requests as cr  # type: ignore
    except ImportError:
        return None
    for candidate in _alternates(url):
        try:
            response = cr.get(candidate, impersonate="chrome", timeout=timeout)
            if response.status_code == 200:
                return response.json()
        except Exception:  # noqa: BLE001 - yedeğe düşülür
            continue
    return None


def get_text(url: str, timeout: int = 40, impersonate: bool = False) -> str:
    if impersonate:
        try:
            from curl_cffi import requests as cr  # type: ignore

            response = cr.get(url, impersonate="chrome", timeout=timeout)
            response.raise_for_status()
            return response.text
        except ImportError:
            pass
    return _get(url, timeout).text


def get_json(url: str, timeout: int = 40):
    if "finance.yahoo.com" in url:
        data = _impersonated_json(url, timeout)
        if data is not None:
            return data
    return _get(url, timeout).json()
