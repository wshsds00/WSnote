import hashlib

from app.core.config import Config
from app.core.embeddings import FakeEmbedder, build_embedder, SentenceEmbedder


def test_fake_embedder_deterministic_and_dim():
    emb = FakeEmbedder(dim=4)
    v1 = emb.embed(["hello"])
    v2 = emb.embed(["hello"])
    assert v1 == v2
    assert len(v1[0]) == 4
    assert all(isinstance(x, float) for x in v1[0])


def test_fake_distinguishes_texts():
    emb = FakeEmbedder(dim=8)
    a = emb.embed(["JVM 内存模型"])[0]
    b = emb.embed(["Redis 缓存"])[0]
    assert a != b


def test_build_embedder_offline_returns_fake():
    cfg = Config()
    cfg.embedding_model = "__missing_model__"
    e = build_embedder(cfg)
    assert isinstance(e, FakeEmbedder)
