from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .controllers import health_controller, learning_controller, prediction_controller
from .repositories.gold_repository import gold_repository
from .services.automatic_learning_service import automatic_learning_service


def create_app() -> FastAPI:
    application = FastAPI(title="Gold Model Learning API", version="1.1.0")
    application.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
    application.include_router(health_controller.router)
    application.include_router(prediction_controller.router, prefix="/v1")
    application.include_router(learning_controller.router, prefix="/v1")

    @application.on_event("startup")
    def startup() -> None:
        gold_repository.initialize()
        automatic_learning_service.start()

    @application.on_event("shutdown")
    async def shutdown() -> None:
        await automatic_learning_service.stop()

    return application


app = create_app()
