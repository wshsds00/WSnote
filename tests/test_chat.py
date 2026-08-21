from app.core.config import Config
from app.core.llm import FakeLLM
from app.retrieval.hybrid import RetrievalHit
from app.chat.service import ChatService
from app.chat.service import Citation, ChatAnswer


class FakeSearcher:
    def __init__(self, hits=None):
        self.hits = hits or [RetrievalHit("c1", "n1", "JVM", "JVM 内存 堆", 0.9)]

    def search(self, query, k=5, use_rerank=False):
        return self.hits


def test_answer_with_citations():
    svc = ChatService(FakeLLM(), FakeSearcher())
    ans = svc.answer("JVM 内存")
    assert ans.citations and ans.citations[0].note_id == "n1"
    assert "JVM" in ans.answer
    assert ans.degraded is False


class OffLLM:
    def complete(self, messages):
        raise AssertionError("不应调用")
    def available(self):
        return False


def test_answer_degrades_when_llm_off():
    svc = ChatService(OffLLM(), FakeSearcher())
    ans = svc.answer("JVM 内存")
    assert ans.degraded is True
    assert ans.answer == "" or "检索" in ans.answer  # 返回仅检索提示
