from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .controllers import health_controller, learning_controller, prediction_controller
from .services.automatic_learning_service import automatic_learning_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    automatic_learning_service.start()
    yield
    await automatic_learning_service.stop()


def create_app() -> FastAPI:
    application = FastAPI(title="Gold Model Learning API", version="1.2.0", lifespan=lifespan)
    application.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
    application.include_router(health_controller.router)
    application.include_router(prediction_controller.router, prefix="/v1")
    application.include_router(learning_controller.router, prefix="/v1")

    return application


app = create_app()
