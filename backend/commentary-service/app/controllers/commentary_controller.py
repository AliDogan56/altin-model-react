from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from ..models.api_models import CommentaryOut
from ..services.commentary_job_service import commentary_job_service
from ..services.commentary_store import commentary_store
from .admin_auth import require_admin

router = APIRouter(prefix="/commentary", tags=["commentary"])


def _latest() -> dict:
    latest = commentary_store.latest()
    if latest is None:
        raise HTTPException(404, "Henüz üretilmiş yorum yok")
    return latest


@router.get("/latest", response_model=CommentaryOut)
def latest() -> dict:
    """Her zaman hazır olan son metin; istek üretim tetiklemez (yanıt milisaniye düzeyinde)."""
    return _latest()


@router.get("/latest/text", response_class=PlainTextResponse)
def latest_text() -> str:
    item = _latest()
    body = "\n\n".join(f"{s['title']}\n{s['text']}" for s in item["sections"])
    return f"{item['title']}\n\n{item['headline']}\n\n{item['summary']}\n\n{body}\n\n{item['disclaimer']}"


@router.get("/latest/audio")
def latest_audio():
    """Son yorumun anlatıcı sesi (MP3). Sürüm başına bir kez üretilir; ses yoksa 404 ve arayüz cihaz sesine düşer."""
    path = commentary_store.latest_audio()
    if path is None:
        raise HTTPException(404, "Bu yorum için ses üretilmedi")
    version = path.parent.name
    return FileResponse(path, media_type="audio/mpeg", filename=f"ons-ai-yorumu-{version}.mp3",
                        headers={"ETag": f'"{version}"', "Cache-Control": "public, max-age=86400", "X-Commentary-Version": version})


@router.get("/job")
def job_status() -> dict:
    return commentary_job_service.status()


@router.post("/regenerate", dependencies=[Depends(require_admin)])
def regenerate() -> dict:
    """Tetik kurallarını atlayıp bir sonraki döngüde üretim ister; üretim arka planda koşar."""
    commentary_job_service.force()
    return {"accepted": True, "force_pending": True, "note": "Bir sonraki kontrol döngüsünde üretilecek"}
