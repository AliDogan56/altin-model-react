import asyncio
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

import httpx
from curl_cffi import requests as browser_requests

log = logging.getLogger(__name__)

XAU_PRIMARY_URL = "https://xaus.com/api/v1/history"
# Yedek kaynak: birincil kaynak (xaus.com) 2026-08-31'de bir saatten uzun 503
# döndü ve uç tamamen cevapsız kaldı. Yahoo'nun altın vadeli serisi aynı
# alanları (tarih, kapanış, yüksek, düşük) ve aynı uzunlukta geçmişi veriyor.
# Vadeli fiyat spot'tan ~%0,6 farklı; girdilerin tamamı getiri/oran olduğu için
# model bundan etkilenmez, seri de tek kaynaktan geldiği için kendi içinde
# tutarlıdır (kaynak harmanlanmıyor).
XAU_FALLBACK_URL = ("https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
                    "?range=5y&interval=1d")
# Gün içi seri: momentum ve kırılım gücü hesabının tek girdisi. Birincil kaynak
# yalnız günlük veriyor; 5 dakikalık mumlar **hacimle birlikte** yalnız burada.
# 5 günlük pencere, bir önceki seansın kapanışını ve gün içi oynaklık
# referansını da kapsar.
XAU_INTRADAY_URL = ("https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
                    "?range=5d&interval=5m")


def yahoo_to_bars(payload: dict) -> list[dict]:
    """Yahoo gün içi yanıtını `t/o/h/l/c/v` mumlarına çevirir.

    Eksik mumlar (seans dışı boş kutular) atlanır. Hacim kaynakta bazen 0 ya da
    None gelir; alan korunur ve tüketiciye hacmin gerçekten var olup olmadığını
    ayırt etme imkânı bırakılır.
    """
    results = (payload.get("chart") or {}).get("result") or []
    if not results:
        raise httpx.RequestError("Gün içi altın kaynağı beklenen gövdeyi döndürmedi")
    result = results[0]
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    volumes = quote.get("volume") or []
    bars = []
    for index, stamp in enumerate(result.get("timestamp") or []):
        close = _at(quote.get("close"), index)
        high, low, opened = (_at(quote.get("high"), index), _at(quote.get("low"), index),
                             _at(quote.get("open"), index))
        if close is None or high is None or low is None:
            continue
        volume = _at(volumes, index)
        bars.append({
            "t": datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
            "o": round(float(opened if opened is not None else close), 2),
            "h": round(float(high), 2), "l": round(float(low), 2),
            "c": round(float(close), 2),
            "v": int(volume) if volume else 0,
        })
    if not bars:
        raise httpx.RequestError("Gün içi altın kaynağında kullanılabilir mum yok")
    bars.sort(key=lambda bar: bar["t"])
    return bars


def _at(values, index):
    return values[index] if values and index < len(values) else None


def yahoo_to_points(payload: dict) -> dict:
    """Yahoo grafik yanıtını birincil kaynağın gövdesine çevirir.

    Eksik günler (tatil, yarım kayıt) atlanır; tüketiciler `points` içindeki
    her satırın dolu olduğunu varsayıyor.
    """
    results = (payload.get("chart") or {}).get("result") or []
    if not results:
        raise httpx.RequestError("Yedek altın kaynağı beklenen gövdeyi döndürmedi")
    result = results[0]
    stamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    points = []
    for stamp, close, high, low in zip(stamps, quote.get("close", []),
                                       quote.get("high", []), quote.get("low", [])):
        if close is None or high is None or low is None:
            continue
        day = datetime.fromtimestamp(stamp, timezone.utc).date().isoformat()
        points.append({"d": day, "c": round(float(close), 2),
                       "h": round(float(high), 2), "l": round(float(low), 2)})
    if not points:
        raise httpx.RequestError("Yedek altın kaynağında kullanılabilir gün yok")
    points.sort(key=lambda row: row["d"])
    return {"symbol": "XAUUSD", "interval": "daily", "currency": "USD", "unit": "ounce",
            "points": points, "count": len(points), "source": "yahoo:GC=F", "fallback": True}


class MarketDataService:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, object]] = {}

    async def _get(self, key: str, url: str, ttl: int, *, as_text: bool = False):
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < ttl:
            return cached[1]
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "GoldModelDashboard/1.1"}) as client:
            response = await client.get(url)
            response.raise_for_status()
            value = response.text if as_text else response.json()
        self._cache[key] = (time.monotonic(), value)
        return value

    async def xau_history(self) -> dict:
        """Birincil kaynak; erişilemezse yedek kaynağa düşer.

        Kaynak düştüğünde uç 502 veriyordu ve grafik tamamen boş kalıyordu.
        Yedek aynı gövdeyi döndürdüğü için tüketicilerde değişiklik gerekmiyor.
        """
        try:
            return await self._get("xau-history", XAU_PRIMARY_URL, 300)
        except (httpx.HTTPError, TimeoutError) as error:
            log.warning("Birincil altın kaynağı erişilemedi (%s); yedeğe düşülüyor", error)
            return yahoo_to_points(await self._get("xau-fallback", XAU_FALLBACK_URL, 300))

    async def xau_intraday(self) -> dict:
        """5 dakikalık gün içi mumlar; momentum hesabının veri kaynağı.

        Önbellek 60 sn: mum aralığı 5 dakika olduğu için daha sık çekmek yeni
        bilgi getirmez, kaynağı gereksiz yorar.
        """
        bars = yahoo_to_bars(await self._get("xau-intraday", XAU_INTRADAY_URL, 60))
        return {"symbol": "XAUUSD", "interval": "5m", "source": "yahoo:GC=F",
                "bars": bars, "count": len(bars)}

    async def fred_series(self, series_id: str) -> str:
        safe_id = re.sub(r"[^A-Z0-9_]", "", series_id.upper())
        if not safe_id:
            raise ValueError("FRED seri kimliği gerekli")
        start = (datetime.now(timezone.utc) - timedelta(days=800)).date().isoformat()
        cached = self._cache.get(f"fred:{safe_id}")
        if cached and time.monotonic() - cached[0] < 900:
            return str(cached[1])
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={safe_id}&cosd={start}"
        try:
            response = await asyncio.to_thread(
                browser_requests.get, url, impersonate="chrome", timeout=30,
                headers={"User-Agent": "GoldModelDashboard/1.1"},
            )
            response.raise_for_status()
        except Exception as error:
            raise httpx.RequestError(f"FRED isteği başarısız: {error}") from error
        csv = response.text
        if not csv.startswith(f"observation_date,{safe_id}"):
            raise httpx.RequestError("FRED beklenen CSV içeriğini döndürmedi")
        self._cache[f"fred:{safe_id}"] = (time.monotonic(), csv)
        return csv

    async def news(self) -> dict:
        url = "https://news.google.com/rss/search?q=gold+Federal+Reserve+inflation+Treasury+yield&hl=en-US&gl=US&ceid=US:en"
        xml = await self._get("gold-news", url, 600, as_text=True)
        root = ElementTree.fromstring(xml)
        articles = []
        for item in root.findall(".//item")[:10]:
            source = item.find("source")
            articles.append({
                "title": item.findtext("title", ""),
                "url": item.findtext("link", ""),
                "source": source.text if source is not None and source.text else "",
                "published": item.findtext("pubDate", ""),
            })
        return {"articles": articles}


market_data_service = MarketDataService()
