from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .controllers import commentary_controller, health_controller
from .database import initialize
from .services.commentary_job_service import commentary_job_service
from .services.llm_config import load_llm_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Ayarlar ayağa kalkmadan önce doğrulanır: eksik anahtar ya da rol varsa servis başlamaz.
    problems = load_llm_settings().validate(settings.pipeline_mode)
    if problems:
        raise RuntimeError("LLM ayarı eksik, commentary-service başlatılmadı:\n  - " + "\n  - ".join(problems))
    initialize()
    commentary_job_service.start()
    yield
    await commentary_job_service.stop()


def create_app() -> FastAPI:
    application = FastAPI(title="Gold Commentary Service", version="1.0.0", lifespan=lifespan)
    application.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
    application.include_router(health_controller.router)
    application.include_router(commentary_controller.router, prefix="/v1")
    return application


app = create_app()
