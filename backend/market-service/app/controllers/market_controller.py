from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Query, Response

from ..services.market_data_service import market_data_service
from ..services.technical.assemble import BLOCKS
from ..services.technical.pivots import PivotMethod, PivotPeriod
from ..services.technical_service import SessionUnavailable, parse_include, technical_service

router = APIRouter(prefix="/market", tags=["market-data"])

TECHNICAL_PATH = "/v1/market/xau/technical"
# Eski uç kaldırılmadı, işaretlendi: istemciler önce yeni uca geçer, sonra bu
# yol düşer. `Link ... successor-version` (RFC 8594) halefi makine okunur kılar.
DEPRECATION_HEADERS = {"Deprecation": "true", "Link": f'<{TECHNICAL_PATH}>; rel="successor-version"'}

# Sorgu parametreleri enum değerlerinden türetilir (küçük/büyük harf ikisi de
# geçerli); liste elle yazılsaydı enum'a yeni yöntem eklenince burası sessizce
# geride kalırdı. Literal dışı değer FastAPI tarafından 422 ile reddedilir.
PivotMethodParam = Literal[tuple(v for m in PivotMethod for v in (m.value, m.value.lower()))]
PivotPeriodParam = Literal[tuple(v for p in PivotPeriod for v in (p.value, p.value.lower()))]


async def upstream(call, *, headers: dict[str, str] | None = None):
    try:
        return await call
    except SessionUnavailable as error:
        # Seans yeni başladıysa yeterli mum olmayabilir; bu bir arıza değil.
        raise HTTPException(503, str(error), headers=headers) from error
    except ValueError as error:
        raise HTTPException(400, str(error), headers=headers) from error
    except (httpx.HTTPError, TimeoutError) as error:
        raise HTTPException(502, f"Harici veri kaynağına ulaşılamadı: {error}", headers=headers) from error


@router.get("/xau")
async def xau_history() -> dict:
    return await upstream(market_data_service.xau_history())


@router.get("/xau/intraday")
async def xau_intraday() -> dict:
    """5 dakikalık gün içi mumlar (hacim dahil)."""
    return await upstream(market_data_service.xau_intraday())


@router.get("/xau/technical")
async def xau_technical(
    response: Response,
    pivot_method: PivotMethodParam = Query("CLASSIC", description="Başlık pivot yöntemi (büyük/küçük harf serbest)"),
    pivot_period: PivotPeriodParam = Query("WEEKLY", description="Başlık pivot dönemi (büyük/küçük harf serbest)"),
    include: str | None = Query(None, description="Virgülle ayrılmış blok adları; boş = hepsi. Bloklar: " + ", ".join(BLOCKS)),
) -> dict:
    """Tek yanıtta teknik analiz: günlük mumlar, seans momentumu, göstergeler,
    pivotlar, yapısal bölgeler, günlük momentum, iki taraflı kırılım ve trend.

    Yanıt girdi anahtarıyla önbelleklenir; anahtar `ETag` olarak döner ve
    `meta.cache` hangi hesaptan geldiğini söyler. `Cache-Control: no-cache`
    saklamayı değil doğrulamadan sunmayı yasaklar: girdi 5 dakikada bir değişir.
    """
    try:
        blocks = parse_include(include)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    out = await upstream(technical_service.technical(PivotMethod(pivot_method.upper()),
                                                     PivotPeriod(pivot_period.upper()), blocks))
    response.headers["ETag"] = f'"{out["meta"]["cache"]["cache_key"]}"'
    response.headers["Cache-Control"] = "no-cache"
    return out


@router.get("/xau/momentum", deprecated=True)
async def xau_momentum(response: Response) -> dict:
    """Gün içi momentum gücü ve ilk destek/direncin kırılım olasılığı (eski uç).

    `/xau/technical` içindeki `session` bloğunun ham hâlini döndürür; gövde ve
    hata davranışı eski uçla birebir aynıdır. Yeni istemciler `technical`'ı
    kullanmalı.
    """
    out = await upstream(technical_service.momentum_alias(), headers=DEPRECATION_HEADERS)
    response.headers.update(DEPRECATION_HEADERS)
    return out


@router.get("/fred", response_class=Response)
async def fred_series(id: str = Query(min_length=1)) -> Response:
    csv = await upstream(market_data_service.fred_series(id))
    return Response(csv, media_type="text/csv; charset=utf-8")


@router.get("/news")
async def news() -> dict:
    return await upstream(market_data_service.news())
