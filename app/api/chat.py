import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatIn(BaseModel):
    question: str


@router.post("")
def chat(body: ChatIn, request: Request):
    s = request.app.state.s
    from app.chat.service import ChatService
    ans = ChatService(s.llm, s.searcher).answer(body.question)
    return {"code": 0, "data": {"answer": ans.answer,
                                "citations": [c.__dict__ for c in ans.citations],
                                "degraded": ans.degraded}}


@router.post("/stream")
def chat_stream(body: ChatIn, request: Request):
    s = request.app.state.s
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "问题为空")
    from app.chat.service import ChatService
    svc = ChatService(s.llm, s.searcher)
    # LLM 未配置 → 非流式 JSON 降级（仍带引用）
    if not svc.llm.available():
        ans = svc.answer(question)
        return {"code": 0, "data": {"answer": ans.answer,
                                    "citations": [c.__dict__ for c in ans.citations],
                                    "degraded": True}}

    def gen():
        for ev in svc.answer_stream(question):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
