import httpx
from fastapi import APIRouter, HTTPException, Query, Response

from ..services.market_data_service import market_data_service

router = APIRouter(prefix="/market", tags=["market-data"])


async def upstream(call):
    try:
        return await call
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except (httpx.HTTPError, TimeoutError) as error:
        raise HTTPException(502, f"Harici veri kaynağına ulaşılamadı: {error}") from error


@router.get("/binance")
async def binance_history() -> list:
    return await upstream(market_data_service.binance_history())


@router.get("/spot")
async def binance_spot() -> dict:
    return await upstream(market_data_service.binance_spot())


@router.get("/fred", response_class=Response)
async def fred_series(id: str = Query(min_length=1)) -> Response:
    csv = await upstream(market_data_service.fred_series(id))
    return Response(csv, media_type="text/csv; charset=utf-8")


@router.get("/news")
async def news() -> dict:
    return await upstream(market_data_service.news())
