import asyncio
import re
import time
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

import httpx
from curl_cffi import requests as browser_requests


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
        return await self._get("xau-history", "https://xaus.com/api/v1/history", 300)

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
