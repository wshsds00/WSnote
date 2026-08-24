import hashlib
import logging
from pathlib import Path
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


class OnnxEmbedder:
    """本地 ONNX 语义向量（bge-small-zh-v1.5），零网络依赖。

    目录结构（与 HF 官方 ONNX 导出一致）：
        tokenizer.json          BERT 分词器（含 [PAD]/[CLS]/[SEP] 特殊 token）
        onnx/model.onnx         transformer 模型，输出 last_hidden_state
    BGE 的向量取 CLS（首 token）后 L2 归一化。
    """

    def __init__(
        self,
        model_dir: Path,
        dim: int = 512,
        max_length: int = 512,
        batch_size: int = 32,
    ):
        from onnxruntime import InferenceSession  # 惰性导入
        from tokenizers import Tokenizer

        import numpy as np
        self._np = np
        self.dim = dim
        self.max_length = max_length
        self.batch_size = batch_size
        model_dir = Path(model_dir)
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        # BERT 的 pad token 是 id=0 的 [PAD]，显式启用 padding/truncation 保证批次定长
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        self.tokenizer.enable_truncation(max_length=max_length)
        self.session = InferenceSession(
            str(model_dir / "onnx" / "model.onnx"),
            providers=["CPUExecutionProvider"],
        )

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        np = self._np
        enc = self.tokenizer.encode_batch(texts, add_special_tokens=True)
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        tti = np.zeros_like(ids)
        out = self.session.run(
            None,
            {"input_ids": ids, "attention_mask": mask, "token_type_ids": tti},
        )[0]
        cls = out[:, 0, :]  # BGE pooling：CLS（首 token）
        norm = np.linalg.norm(cls, axis=1, keepdims=True)
        cls = cls / np.maximum(norm, 1e-9)  # L2 归一化
        return cls.tolist()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            out.extend(self._embed_batch(texts[i : i + self.batch_size]))
        return out


def build_embedder(config: Config) -> Embedder:
    if config.embedding_model == "__missing_model__":
        logger.warning("离线/缺模型：使用 FakeEmbedder")
        return FakeEmbedder(dim=config.embedding_dim)
    # 1. 本地 ONNX 模型优先（离线可用，无需联网下载）
    if config.embedding_local_path and Path(config.embedding_local_path).exists():
        try:
            return OnnxEmbedder(config.embedding_local_path, dim=config.embedding_dim)
        except Exception as e:
            logger.warning("本地 ONNX 模型加载失败（%s），尝试在线模型", e)
    # 2. 在线 sentence-transformers（联网下载模型）
    try:
        return SentenceEmbedder(config.embedding_model, config.embedding_dim)
    except Exception as e:  # 模型下载/加载失败 → 降级
        logger.warning("embedding 加载失败（%s），降级 FakeEmbedder", e)
        return FakeEmbedder(dim=config.embedding_dim)
