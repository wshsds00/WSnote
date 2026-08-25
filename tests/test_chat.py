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


def test_answer_stream_yields_meta_delta_done():
    svc = ChatService(FakeLLM(), FakeSearcher())
    events = list(svc.answer_stream("JVM 内存"))
    metas = [e for e in events if e["type"] == "meta"]
    deltas = "".join(e["content"] for e in events if e["type"] == "delta")
    assert metas and metas[0]["degraded"] is False
    assert metas[0]["citations"][0]["note_id"] == "n1"
    assert deltas.strip()
    assert events[-1]["type"] == "done"


def test_answer_stream_degrades_when_llm_off():
    svc = ChatService(OffLLM(), FakeSearcher())
    events = list(svc.answer_stream("JVM 内存"))
    assert events[0]["type"] == "meta"
    assert events[0]["degraded"] is True
    assert events[0]["citations"][0]["note_id"] == "n1"
    assert not any(e["type"] == "delta" for e in events)


def test_answer_stream_error_yields_error_event():
    class BoomLLM:
        def available(self):
            return True

        def complete_stream(self, messages):
            raise RuntimeError("boom")

    svc = ChatService(BoomLLM(), FakeSearcher())
    events = list(svc.answer_stream("JVM 内存"))
    assert any(e["type"] == "error" for e in events)
    assert not any(e["type"] == "done" for e in events)
