import os
import sys

# Windows: 将 nvidia 运行时 DLL 目录加入搜索路径（cublas64_12.dll 等）
if sys.platform == "win32":
    site_packages = os.path.join(os.path.dirname(__file__), "..", ".venv", "Lib", "site-packages")
    site_packages = os.path.abspath(site_packages)
    for sub in ("nvidia/cublas/bin", "nvidia/cudnn/bin", "nvidia/cufft/bin",
                "nvidia/curand/bin", "nvidia/cusolver/bin", "nvidia/cusparse/bin",
                "nvidia/nccl/bin", "nvidia/nvjitlink/bin"):
        dll_dir = os.path.join(site_packages, sub)
        if os.path.isdir(dll_dir):
            os.add_dll_directory(dll_dir)
            os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import notes, search, chat, tags, index, process
from app.core.config import Config, get_config
from app.core.db import Database
from app.core.embeddings import build_embedder
from app.core.llm import build_llm
from app.asr.client import build_asr
from app.ingest.ingestor import Ingestor
from app.ingest.vector_store import VectorStore
from app.notes.store import NoteStore
from app.retrieval.bm25 import BM25Index
from app.retrieval.hybrid import HybridSearcher
from app.retrieval.rerank import Reranker


def create_app(config: Config | None = None, note_store=None, db=None,
               ingestor=None, llm=None):
    config = config or get_config()
    ns = note_store or NoteStore(config)
    database = db or Database(config.db_path)
    database.init()
    embedder = build_embedder(config)
    vs = VectorStore(config, database, embedder)
    vs.load_or_reset()
    ing = ingestor or Ingestor(config, ns, database, embedder, vs)
    if len(database.all_chunks()) > 0 and ing.vs.count() == 0:
        ing.rebuild_all()
    bm25 = BM25Index()
    bm25.build(database.all_chunks())
    llm = llm if llm is not None else build_llm(config)
    asr = build_asr(config)
    reranker = Reranker(config.rerank_model)
    searcher = HybridSearcher(config, database, ing.vs, ing.embedder, bm25, reranker)

    app = FastAPI(title="WSnote", version="0.1.0")
    app.state.s = type("S", (), {
        "config": config, "note_store": ns, "db": database,
        "ingestor": ing, "llm": llm, "asr": asr, "searcher": searcher,
    })()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(notes.router)
    app.include_router(search.router)
    app.include_router(chat.router)
    app.include_router(tags.router)
    app.include_router(index.router)
    app.include_router(process.router)
    return app


app = create_app()
