from app.retrieval.bm25 import tokenize, BM25Index
from app.ingest.chunker import Chunk


def make_chunks():
    return [
        Chunk("c1", "n1", "JVM", "JVM 内存模型 堆 栈 垃圾回收", 0),
        Chunk("c2", "n1", "Redis", "Redis 缓存 过期 策略", 0),
    ]


def test_tokenize_chinese_and_latin():
    toks = tokenize("JVM内存模型 Stack")
    assert "jvm" in toks and "内" in toks and "存" in toks and "stack" in toks


def test_bm25_ranks_matching_chunk_first():
    idx = BM25Index()
    idx.build(make_chunks())
    hits = idx.search("垃圾回收", k=2)
    assert hits[0][0] == "c1"


def test_bm25_empty_corpus():
    idx = BM25Index()
    idx.build([])
    assert idx.search("任意", k=1) == []
