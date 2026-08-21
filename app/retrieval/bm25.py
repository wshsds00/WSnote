import math
import re
from rank_bm25 import BM25Okapi

from app.ingest.chunker import Chunk

_TOKEN = re.compile(r"[一-鿿]|[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class _PosIdfOkapi(BM25Okapi):
    """rank_bm25 的 BM25Okapi 在 df = N/2（如 2 篇语料中仅 1 篇出现某词）时
    idf 计算为 log(1.5) - log(1.5) = 0，导致全部文档得分归零、无法区分相关文档。
    改用标准 RSJ +1 变体：idf = log(1 + (N - df + 0.5)/(df + 0.5))，恒 >= 0，
    常见词（df 接近 N）也不会被 <0 过滤全部丢弃。"""

    def _calc_idf(self, nd: dict[str, int]) -> None:
        for word, freq in nd.items():
            self.idf[word] = math.log(
                1 + (self.corpus_size - freq + 0.5) / (freq + 0.5))


class BM25Index:
    def __init__(self) -> None:
        self._bm25 = None
        self._chunks: list[Chunk] = []
        self._index: dict[str, Chunk] = {}

    def build(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        self._index = {c.chunk_id: c for c in chunks}
        if chunks:
            self._bm25 = _PosIdfOkapi([tokenize(c.text) for c in chunks])
        else:
            self._bm25 = None

    def search(self, query: str, k: int) -> list[tuple[str, float]]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [(self._chunks[i].chunk_id, float(scores[i]))
                for i in order if scores[i] > 0][:k]
