from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import notes, search, chat, tags, index, process
from app.core.config import Config, get_config
from app.core.db import Database
from app.core.embeddings import build_embedder
from app.core.llm import build_llm
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
    reranker = Reranker(config.rerank_model)
    searcher = HybridSearcher(config, database, ing.vs, ing.embedder, bm25, reranker)

    app = FastAPI(title="WSnote", version="0.1.0")
    app.state.s = type("S", (), {
        "config": config, "note_store": ns, "db": database,
        "ingestor": ing, "llm": llm, "searcher": searcher,
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
