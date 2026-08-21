import logging
from dataclasses import dataclass

from app.retrieval.hybrid import HybridSearcher, RetrievalHit

logger = logging.getLogger("wsnote.chat")


@dataclass
class Citation:
    note_id: str
    heading_path: str
    text: str


@dataclass
class ChatAnswer:
    answer: str
    citations: list[Citation]
    degraded: bool


_PROMPT = (
    "你是一个个人知识库助手。请仅根据提供的资料回答，不要编造。"
    "若资料不足，明确说明。回答用中文。\n\n资料：\n{context}\n\n问题：{question}"
)


class ChatService:
    def __init__(self, llm, searcher: HybridSearcher):
        self.llm = llm
        self.searcher = searcher

    def answer(self, question: str) -> ChatAnswer:
        hits: list[RetrievalHit] = self.searcher.search(question)
        citations = [
            Citation(note_id=h.note_id, heading_path=h.heading_path, text=h.text[:200])
            for h in hits
        ]
        if not self.llm.available():
            return ChatAnswer(answer="（LLM 未配置）已检索到以下资料，请查看引用。",
                              citations=citations, degraded=True)
        try:
            context = "\n\n".join(f"[{i+1}] {h.text}" for i, h in enumerate(hits))
            messages = [{"role": "user", "content": _PROMPT.format(context=context, question=question)}]
            answer = self.llm.complete(messages)
            return ChatAnswer(answer=answer, citations=citations, degraded=False)
        except Exception:
            logger.exception("LLM 调用失败，已降级为仅检索")
            return ChatAnswer(answer="（LLM 调用失败，已降级为仅检索）",
                              citations=citations, degraded=True)
