from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class Config:
    root_dir: Path = PROJECT_ROOT
    notes_dir: Path = PROJECT_ROOT / "notes"
    data_dir: Path = PROJECT_ROOT / "data"
    db_path: Path | None = None
    faiss_path: Path | None = None
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_local_path: Path | None = PROJECT_ROOT / "models" / "bge-small-zh-v1.5"
    embedding_dim: int = 512
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k: int = 5
    bm25_weight: float = 0.5
    dense_weight: float = 0.5
    rrf_k: int = 60
    use_rerank: bool = False
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_timeout: float = 20.0

    # ASR 语音转写（MiMo，OpenAI 兼容）
    asr_base_url: str = ""
    asr_api_key: str = ""
    asr_model: str = "mimo-v2.5-asr"
    asr_timeout: float = 600.0

    def __post_init__(self) -> None:
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.db_path is None:
            self.db_path = self.data_dir / "wsnote.db"
        if self.faiss_path is None:
            self.faiss_path = self.data_dir / "index.faiss"


def get_config() -> Config:
    return Config()
