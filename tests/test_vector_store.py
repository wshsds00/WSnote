import tempfile
from pathlib import Path

from app.core.config import Config
from app.core.db import Database
from app.core.embeddings import FakeEmbedder
from app.ingest.vector_store import VectorStore


def make_store():
    d = tempfile.mkdtemp()
    cfg = Config(root_dir=Path(d), notes_dir=Path(d) / "notes", data_dir=Path(d) / "data")
    db = Database(cfg.db_path)
    db.init()
    vs = VectorStore(cfg, db, FakeEmbedder(dim=8))
    return vs, db


def test_add_search_persist():
    vs, db = make_store()
    vs.add("c1", vs.embedder.embed(["你好 世界"])[0])
    vs.add("c2", vs.embedder.embed(["完全 不同 内容"])[0])
    assert vs.count() == 2
    res = vs.search(vs.embedder.embed(["你好 世界"])[0], k=2)
    assert res[0][0] == "c1"
    vs.save()
    vs2 = VectorStore(vs.config, db, vs.embedder)
    vs2.load()
    assert vs2.count() == 2
    res2 = vs2.search(vs2.embedder.embed(["你好 世界"])[0], k=2)
    assert res2[0][0] == "c1"


def test_remove_chunks():
    vs, db = make_store()
    vs.add("c1", vs.embedder.embed(["a"])[0])
    vs.add("c2", vs.embedder.embed(["b"])[0])
    vs.remove_chunks(["c1"])
    assert vs.count() == 1
    res = vs.search(vs.embedder.embed(["b"])[0], k=5)
    assert [r[0] for r in res] == ["c2"]
