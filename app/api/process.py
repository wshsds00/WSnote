import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.asr.client import ALLOWED_EXTENSIONS, MAX_FILE_SIZE
from app.process.service import NoteProcessor

router = APIRouter(prefix="/api/process", tags=["process"])

LLM_NOT_CONFIGURED = "LLM 未配置：请在环境变量设置 WSNOTE_LLM_API_KEY 后使用 AI 整理"
ASR_NOT_CONFIGURED = "ASR 未配置：请安装 faster-whisper（本地）或设置环境变量 WSNOTE_ASR_API_KEY（MiMo API）"


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
    return NoteProcessor(s.note_store, s.ingestor, s.llm, getattr(s, "asr", None))


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


@router.post("/transcribe")
async def transcribe(file: UploadFile, request: Request):
    proc = _processor(request)
    if not proc.asr or not proc.asr.available():
        raise HTTPException(400, ASR_NOT_CONFIGURED)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的音频格式：{ext}，支持：{', '.join(sorted(ALLOWED_EXTENSIONS))}")

    audio_bytes = await file.read()
    if len(audio_bytes) == 0:
        raise HTTPException(400, "音频文件为空")
    if len(audio_bytes) > MAX_FILE_SIZE:
        raise HTTPException(400, f"音频文件过大（>{MAX_FILE_SIZE // 1024 // 1024}MB）")

    try:
        text = proc.transcribe_audio(audio_bytes, file.filename or "audio.mp3")
    except Exception as e:
        raise HTTPException(502, f"ASR 转写失败：{e}")

    return {"code": 0, "data": {"text": text}}


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
