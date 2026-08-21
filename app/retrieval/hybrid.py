from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.config import Config
from app.core.db import Database
from app.ingest.vector_store import VectorStore
from app.retrieval.bm25 import BM25Index

if TYPE_CHECKING:
    from app.retrieval.rerank import Reranker  # 仅在类型检查时导入，避免与 rerank.py 的循环依赖


@dataclass
class RetrievalHit:
    chunk_id: str
    note_id: str
    heading_path: str
    text: str
    score: float


def rrf_fuse(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return scores


class HybridSearcher:
    def __init__(self, config: Config, db: Database, vector_store: VectorStore,
                 embedder, bm25: BM25Index, reranker: "Reranker | None" = None):
        self.config = config
        self.db = db
        self.vs = vector_store
        self.embedder = embedder
        self.bm25 = bm25
        self.reranker = reranker

    def search(self, query: str, k: int = 5, use_rerank: bool = False) -> list[RetrievalHit]:
        if use_rerank and self.reranker is not None:
            candidates = self.search(query, k * 3, use_rerank=False)
            return self.reranker.rerank(query, candidates, k)
        dense_hits = self.vs.search(self.embedder.embed([query])[0], k * 3)
        sparse_hits = self.bm25.search(query, k * 3)
        fused = rrf_fuse([dense_hits and [c for c, _ in dense_hits] or [],
                          [c for c, _ in sparse_hits]], self.config.rrf_k)
        ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:k]
        out = []
        for chunk_id, score in ranked:
            ch = self.db.get_chunk(chunk_id)
            if ch:
                out.append(RetrievalHit(chunk_id, ch.note_id, ch.heading_path, ch.text, score))
        return out
