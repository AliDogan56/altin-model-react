from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import initialize
from .controllers import health_controller, market_controller


def create_app() -> FastAPI:
    application = FastAPI(title="Gold Market Data Service", version="1.0.0")
    application.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
    application.include_router(health_controller.router)
    application.include_router(market_controller.router, prefix="/v1")

    @application.on_event("startup")
    def startup() -> None:
        initialize()

    return application


app = create_app()
