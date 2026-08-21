from app.retrieval.rerank import Reranker
from app.retrieval.hybrid import RetrievalHit


def hits():
    return [
        RetrievalHit("c1", "n1", "JVM", "JVM 内存 堆 栈 垃圾回收", 0.5),
        RetrievalHit("c2", "n2", "Redis", "Redis 缓存 过期", 0.4),
    ]


def test_rerank_unavailable_passthrough():
    r = Reranker(model_name="__unavailable__")
    assert r.available() is False
    out = r.rerank("垃圾回收", hits(), 2)
    assert [h.chunk_id for h in out] == ["c1", "c2"]  # 原序


def test_rerank_available_orders_by_score(monkeypatch):
    r = Reranker(model_name="__fake__")
    monkeypatch.setattr(r, "available", lambda: True)

    class FakeModel:
        def compute_score(self, pairs, normalize=True):
            return [0.2, 0.9]  # c2 打分更高 → 重排后 c2 在前

    monkeypatch.setattr(r, "_model", FakeModel())
    out = r.rerank("垃圾回收", hits(), 2)
    assert [h.chunk_id for h in out] == ["c2", "c1"]
    assert len(r.rerank("垃圾回收", hits(), 1)) == 1
