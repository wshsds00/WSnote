from app.retrieval.hybrid import rrf_fuse, HybridSearcher
from app.core.config import Config
from app.core.db import Database
from app.core.embeddings import FakeEmbedder
from app.ingest.vector_store import VectorStore
from app.ingest.chunker import Chunk
from app.retrieval.bm25 import BM25Index
import tempfile
from pathlib import Path


def test_rrf_fuse():
    fused = rrf_fuse([["a", "b", "c"], ["a", "b", "d"]], k=60)
    assert fused["a"] > fused["b"] > fused["c"]
    assert "d" in fused


def test_hybrid_search_returns_hits():
    d = tempfile.mkdtemp()
    cfg = Config(root_dir=Path(d), notes_dir=Path(d) / "notes", data_dir=Path(d) / "data")
    db = Database(cfg.db_path); db.init()
    emb = FakeEmbedder(dim=8)
    vs = VectorStore(cfg, db, emb); vs.reset()
    chunks = [
        Chunk("c1", "n1", "JVM", "JVM 内存模型 堆 垃圾回收", 0),
        Chunk("c2", "n2", "Redis", "Redis 缓存 过期", 0),
    ]
    db.insert_chunks(chunks)
    for c, v in zip(chunks, emb.embed([c.text for c in chunks])):
        vs.add(c.chunk_id, v)
    bm25 = BM25Index(); bm25.build(chunks)
    searcher = HybridSearcher(cfg, db, vs, emb, bm25)
    hits = searcher.search("垃圾回收", k=2)
    assert hits and hits[0].chunk_id == "c1"
    assert hits[0].text.startswith("JVM")
