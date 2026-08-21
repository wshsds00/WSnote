from fastapi import APIRouter, Request
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
