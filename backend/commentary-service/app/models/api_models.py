from pydantic import BaseModel


class CommentarySection(BaseModel):
    id: str
    title: str
    text: str


class LivePrice(BaseModel):
    price: float
    source: str
    time_utc: str | None = None
    change_vs_fix_pct: float | None = None
    change_vs_fix_usd: float | None = None
    change_vs_prev_close_pct: float | None = None
    atr_multiple: float | None = None


class OfficialFix(BaseModel):
    date: str
    price: float


class NarrationSegment(BaseModel):
    id: str
    start: float
    end: float


class NarrationOut(BaseModel):
    voice: str
    model: str
    duration_seconds: float
    bitrate_kbps: int
    bytes: int
    segments: list[NarrationSegment]
    estimated: bool = True


class CommentaryOut(BaseModel):
    version: str
    as_of: str
    generated_at: str
    age_seconds: int | None = None
    run_mode: str
    trigger: dict
    live: LivePrice | None = None
    official_fix: OfficialFix | None = None
    title: str
    headline: str
    summary: str
    sections: list[CommentarySection]
    usage: dict
    durations_seconds: dict
    disclaimer: str
    narration: NarrationOut | None = None
