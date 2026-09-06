"""Teknik analiz paketinin asenkron kabuğu.

Saf paket (`technical/`) ağ, saat ve önbellek bilmez; bu modül üçünü sağlar:
günlük ve gün içi yükü çeker, girdilerden önbellek anahtarını üretir, hesabı
iş parçacığında ve tek uçuş kilidinde çalıştırır, DTO'ya çevirir. HTTP de
bilmez — durum kodu eşlemesi denetleyicidedir; buradan yalnız alan hataları
çıkar (`SessionUnavailable`, üst kaynağın kendi hataları, `ValueError`).

Hata politikası:
- Günlük seri **zorunlu** girdi: alınamazsa hata olduğu gibi yükselir ve
  denetleyici eskiden `/xau` için yaptığı gibi 502'ye çevirir.
- Gün içi seri **isteğe bağlı**: alınamazsa uyarı loglanır ve analiz günlük
  çerçeveye düşer (`session.status = INTRADAY_UNAVAILABLE`, referans günlük
  kapanış). Pivot, bölge, trend ve gösterge blokları gün içi olmadan da
  anlamlıdır; Yahoo'nun 5 dakikalık akışı yüzünden bütün sayfayı boş bırakmak
  yanlış olurdu.
- `/xau/momentum` takma adı eski ucun sözleşmesini korur: seans bloğu
  hesaplanamıyorsa (mum azlığı, sıfır oynaklık) eski ValueError metniyle
  `SessionUnavailable` (→ 503); gün içi alınamadıysa o kaynağın kendi hatası
  (→ 502); günlük seri alınamadıysa eskisi gibi boş merdivenle devam.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Sequence

from .market_data_service import MarketDataService, market_data_service
from .technical import assemble, session
from .technical.assemble import TechnicalAnalysis
from .technical.cache import AnalysisCache, Clock, analysis_key, utc_now
from .technical.config import CONFIG, TechnicalConfig
from .technical.pivots import PivotMethod, PivotPeriod

log = logging.getLogger(__name__)


class SessionUnavailable(RuntimeError):
    """Seans bloğu bu girdiyle hesaplanamıyor (mum azlığı / sıfır oynaklık).

    Bir arıza değil, veri durumu: seans yeni başlamış olabilir. Eski uç bunu
    503 ile bildiriyordu; metin `technical.session.momentum`'un ValueError'ıdır
    ve olduğu gibi taşınır ki istemci tarafındaki eşleşmeler bozulmasın.
    """


@dataclass(frozen=True)
class Computed:
    analysis: TechnicalAnalysis
    cache: dict[str, Any]
    intraday_error: Exception | None


def parse_include(raw: str | None) -> list[str] | None:
    """`?include=pivots,breakout` → blok listesi; boş → None (hepsi).

    Bilinmeyen ad → ValueError (`assemble.select_blocks` metniyle). Doğrulama
    veri çekilmeden önce yapılır: hatalı istek üst kaynağa tek istek attırmaz.
    """
    if raw is None or not raw.strip():
        return None
    names = [part.strip() for part in raw.split(",") if part.strip()]
    return sorted(assemble.select_blocks(names))


class TechnicalService:
    def __init__(self, data: MarketDataService | None = None, *, cfg: TechnicalConfig = CONFIG,
                 clock: Clock = utc_now, cache: AnalysisCache[TechnicalAnalysis] | None = None) -> None:
        self.data = data if data is not None else market_data_service
        self.cfg = cfg
        self.clock = clock
        self.cache: AnalysisCache[TechnicalAnalysis] = cache if cache is not None else AnalysisCache(cfg.cache_ttl_seconds, clock=clock)

    async def compute(self) -> Computed:
        """Günlük seri zorunlu (hatası yükselir), gün içi isteğe bağlı."""
        return await self._compute(await self.data.xau_history())

    async def technical(self, pivot_method: PivotMethod = PivotMethod.CLASSIC,
                        pivot_period: PivotPeriod = PivotPeriod.WEEKLY,
                        include: Sequence[str] | None = None) -> dict[str, Any]:
        blocks = sorted(assemble.select_blocks(include))
        computed = await self.compute()
        # DTO 1257 mumu satır satır kurar (~10 ms); analizle aynı sebeple
        # döngüden uzak tutulur. `cache` meta'sı yanıta `meta.cache` olarak girer
        # ve denetleyici ETag'i oradan okur.
        return await asyncio.to_thread(assemble.to_dict, computed.analysis, pivot_method=pivot_method,
                                       pivot_period=pivot_period, include=blocks, cache=computed.cache, cfg=self.cfg)

    async def momentum_alias(self) -> dict[str, Any]:
        """Eski `/xau/momentum` gövdesi: `analysis.session`'ın ham hâli.

        DTO'daki `session` bloğu durum alanları ekler (`status`, `frame`,
        `market_state`...); eski istemciler tam anahtar kümesine bağlı olduğu
        için burada DTO değil hesaplanan sözlüğün kendisi döner.
        """
        try:
            daily = await self.data.xau_history()
        except Exception as error:  # noqa: BLE001 — eski uç da her hatada devam ediyordu
            # Günlük seri burada yalnız merdiven içindir; alınamazsa eski uç boş
            # seriyle devam ediyor ve merdiveni gün içi akıştan kuruyordu. Davranış
            # korunur, fark şu: hata artık sessizce yutulmaz, loglanır.
            log.warning("Günlük altın serisi alınamadı (%s); momentum merdiveni gün içi akıştan kurulacak", error)
            payload = await self.data.xau_intraday()  # gün içi de yoksa hata eskisi gibi yükselir
            return await self._session_or_raise(payload.get("bars") or [], [])
        computed = await self._compute(daily)
        analysis = computed.analysis
        if analysis.session is not None:
            return analysis.session
        if computed.intraday_error is not None:
            # Eski uç gün içi kaynağı doğrudan çekiyor, hatası 502 oluyordu;
            # aynı istisna aynı eşlemeden geçsin diye olduğu gibi yükseltilir.
            raise computed.intraday_error
        raise SessionUnavailable(analysis.session_error or "Gün içi seri yok; momentum hesaplanamaz")

    async def _compute(self, daily: dict[str, Any]) -> Computed:
        intraday, intraday_error = await self._intraday()
        now = self.clock()
        key = analysis_key(daily, intraday, today=now.date(), config_hash=self.cfg.config_hash())
        analysis, meta = await self.cache.get_or_compute(
            key, lambda: asyncio.to_thread(assemble.analyze, daily, intraday, now=now, cfg=self.cfg))
        return Computed(analysis, meta, intraday_error)

    async def _intraday(self) -> tuple[dict[str, Any] | None, Exception | None]:
        try:
            return await self.data.xau_intraday(), None
        except Exception as error:  # noqa: BLE001 — gün içi yedek bilgidir, hiçbir hatası ölümcül değil
            log.warning("Gün içi altın kaynağı alınamadı (%s); analiz günlük çerçeveye düşüyor", error)
            return None, error

    @staticmethod
    async def _session_or_raise(bars: Sequence[dict], daily: Sequence[dict]) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(session.momentum, list(bars), daily=list(daily))
        except ValueError as error:
            raise SessionUnavailable(str(error)) from error


technical_service = TechnicalService()
