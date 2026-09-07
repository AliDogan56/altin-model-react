import httpx
from fastapi import APIRouter, HTTPException, Query, Response

from ..services.market_data_service import market_data_service
from ..services.momentum_service import momentum

router = APIRouter(prefix="/market", tags=["market-data"])


async def upstream(call):
    try:
        return await call
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except (httpx.HTTPError, TimeoutError) as error:
        raise HTTPException(502, f"Harici veri kaynağına ulaşılamadı: {error}") from error


@router.get("/xau")
async def xau_history() -> dict:
    return await upstream(market_data_service.xau_history())


@router.get("/xau/intraday")
async def xau_intraday() -> dict:
    """5 dakikalık gün içi mumlar (hacim dahil)."""
    return await upstream(market_data_service.xau_intraday())


@router.get("/xau/momentum")
async def xau_momentum() -> dict:
    """Gün içi momentum gücü ve ilk destek/direncin kırılım olasılığı.

    Eşikler sabit değil; o seansın oynaklığına göre uyarlanır.
    """
    payload = await upstream(market_data_service.xau_intraday())
    # Seviye merdiveni günlük mumdan kurulur: gün içi akışın önceki seansı
    # kırpık geliyor ve pivotları olduğundan dar çıkarıyordu (ölçüldü:
    # 32,14 $ aralık, gerçeği 56,0 $). Günlük seri gelmezse momentum yine
    # hesaplanır, yalnız merdiven kabalaşır.
    try:
        history = await market_data_service.xau_history()
        daily = history.get("points", [])
    except Exception:
        daily = []
    try:
        return momentum(payload["bars"], daily=daily)
    except ValueError as error:
        # Seans yeni başladıysa yeterli mum olmayabilir; bu bir arıza değil.
        raise HTTPException(503, str(error)) from error


@router.get("/fred", response_class=Response)
async def fred_series(id: str = Query(min_length=1)) -> Response:
    csv = await upstream(market_data_service.fred_series(id))
    return Response(csv, media_type="text/csv; charset=utf-8")


@router.get("/news")
async def news() -> dict:
    return await upstream(market_data_service.news())
