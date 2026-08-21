import hashlib
import logging
from typing import Protocol

from app.core.config import Config

logger = logging.getLogger("wsnote.embeddings")


class Embedder(Protocol):
    dim: int
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbedder:
    """确定性假 embedding：同文本同向量，零网络依赖。"""
    def __init__(self, dim: int = 8):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8")).digest()
            # sha256 摘要仅 32 字节，dim > 32 时循环取字节以保持正确维度
            v = [float(h[i % len(h)] / 255.0) for i in range(self.dim)]
            out.append(v)
        return out


class SentenceEmbedder:
    def __init__(self, model_name: str, dim: int):
        from sentence_transformers import SentenceTransformer  # 惰性导入
        self.model = SentenceTransformer(model_name)
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]


def build_embedder(config: Config) -> Embedder:
    if config.embedding_model == "__missing_model__":
        logger.warning("离线/缺模型：使用 FakeEmbedder")
        return FakeEmbedder(dim=config.embedding_dim)
    try:
        return SentenceEmbedder(config.embedding_model, config.embedding_dim)
    except Exception as e:  # 模型下载/加载失败 → 降级
        logger.warning("embedding 加载失败（%s），降级 FakeEmbedder", e)
        return FakeEmbedder(dim=config.embedding_dim)
