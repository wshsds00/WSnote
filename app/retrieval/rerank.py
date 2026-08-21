import logging

from app.retrieval.hybrid import RetrievalHit

logger = logging.getLogger("wsnote.rerank")


class Reranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model_name = model_name
        self._model = None

    def available(self) -> bool:
        if self._model is not None:
            return True
        try:
            from FlagEmbedding import FlagReranker  # 惰性导入
            self._model = FlagReranker(self.model_name, use_fp16=False)
            return True
        except Exception as e:
            logger.warning("reranker 不可用（%s），跳过重排", e)
            return False

    def rerank(self, query: str, hits: list[RetrievalHit], top_k: int) -> list[RetrievalHit]:
        if not self.available():
            return hits[:top_k]
        pairs = [[query, h.text] for h in hits]
        scores = self._model.compute_score(pairs, normalize=True)
        order = sorted(range(len(hits)), key=lambda i: scores[i], reverse=True)
        return [hits[i] for i in order][:top_k]
