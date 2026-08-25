import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.process.service import NoteProcessor

router = APIRouter(prefix="/api/process", tags=["process"])

LLM_NOT_CONFIGURED = "LLM 未配置：请在环境变量设置 WSNOTE_LLM_API_KEY 后使用 AI 整理"


class ImportIn(BaseModel):
    text: str
    mode: str = "single"  # single | split_h1
    title: str = ""
    tags: list[str] | None = None


class AnalyzeIn(BaseModel):
    text: str
    mode: str = "interview"  # interview | general | meeting


def _processor(request: Request) -> NoteProcessor:
    s = request.app.state.s
    return NoteProcessor(s.note_store, s.ingestor, s.llm)


@router.post("/import")
def import_text(body: ImportIn, request: Request):
    try:
        created, skipped = _processor(request).import_text(
            body.text, body.mode, body.title, body.tags or [])
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"code": 0, "data": {
        "created": [m.__dict__ for m in created],
        "skipped": skipped,
    }}


@router.post("/analyze")
def analyze(body: AnalyzeIn, request: Request):
    proc = _processor(request)
    try:
        proc.validate_analyze(body.text, body.mode)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # LLM 不可用 → 非流式 JSON 降级
    if not proc.llm.available():
        return {"code": 0, "data": {
            "markdown": "", "degraded": True, "mode": body.mode,
            "message": LLM_NOT_CONFIGURED,
        }}

    def gen():
        for ev in proc.analyze_stream(body.text, body.mode):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
