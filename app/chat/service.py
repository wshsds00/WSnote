import logging
from dataclasses import dataclass
from typing import Iterator

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

    def answer_stream(self, question: str) -> Iterator[dict]:
        """流式回答，产出事件 dict：meta / delta / error / done。

        meta 事件携带 citations（检索结果），随后逐个产出 delta。
        """
        hits: list[RetrievalHit] = self.searcher.search(question)
        citations = [
            Citation(note_id=h.note_id, heading_path=h.heading_path, text=h.text[:200])
            for h in hits
        ]
        citation_dicts = [c.__dict__ for c in citations]
        if not self.llm.available():
            yield {"type": "meta", "degraded": True, "citations": citation_dicts,
                   "message": "LLM 未配置：已降级为仅检索，仅返回命中的原文片段"}
            return
        try:
            context = "\n\n".join(f"[{i+1}] {h.text}" for i, h in enumerate(hits))
            messages = [{"role": "user", "content": _PROMPT.format(context=context, question=question)}]
            yield {"type": "meta", "degraded": False, "citations": citation_dicts}
            received = False
            for chunk in self.llm.complete_stream(messages):
                if not chunk:
                    continue
                received = True
                yield {"type": "delta", "content": chunk}
            if not received:
                yield {"type": "error", "message": "LLM 返回空内容"}
                return
            yield {"type": "done"}
        except Exception:
            logger.exception("LLM 流式调用失败，已降级为仅检索")
            yield {"type": "error", "message": "AI 回答调用失败，请稍后重试"}
