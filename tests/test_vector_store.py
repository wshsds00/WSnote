import tempfile
from pathlib import Path

from app.core.config import Config
from app.core.db import Database
from app.core.embeddings import FakeEmbedder
from app.ingest.ingestor import Ingestor
from app.ingest.vector_store import VectorStore
from app.notes.store import NoteStore


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


def test_numpy_fallback_roundtrip(monkeypatch):
    # faiss 缺失时的纯 numpy 兜底路径必须走同一条契约（add/search/save/load/remove）
    monkeypatch.setattr("app.ingest.vector_store._HAS_FAISS", False)
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
    vs2.remove_chunks(["c2"])
    assert vs2.count() == 1


def test_load_or_reset_reloads_numpy_fallback(monkeypatch):
    # numpy 兜底模式下 save() 写 index.np.json，load_or_reset 必须能识别并重载
    monkeypatch.setattr("app.ingest.vector_store._HAS_FAISS", False)
    vs, db = make_store()
    vs.add("c1", vs.embedder.embed(["你好 世界"])[0])
    vs.save()
    vs2 = VectorStore(vs.config, db, vs.embedder)
    vs2.load_or_reset()
    assert vs2.count() == 1


def test_bootstrap_rebuilds_missing_index():
    # 模拟：notes 已索引、faiss 文件被删除后，bootstrap 逻辑应从 notes 全量重建
    d = tempfile.mkdtemp()
    cfg = Config(root_dir=Path(d), notes_dir=Path(d) / "notes", data_dir=Path(d) / "data")
    ns = NoteStore(cfg)
    db = Database(cfg.db_path); db.init()
    emb = FakeEmbedder(dim=8)
    vs = VectorStore(cfg, db, emb); vs.reset()
    ing = Ingestor(cfg, ns, db, emb, vs)
    ns.create("A", "# 标题\n内容A")
    ing.index_note("A")
    assert vs.count() == 1
    vs.save()

    # 删除 faiss 索引文件（模拟丢失/损坏）
    cfg.faiss_path.unlink(missing_ok=True)
    cfg.faiss_path.with_suffix(".np.json").unlink(missing_ok=True)

    # bootstrap 等价逻辑
    vs2 = VectorStore(cfg, db, emb)
    vs2.load_or_reset()
    assert vs2.count() == 0  # 索引文件已丢 → reset 为空
    ing2 = Ingestor(cfg, ns, db, emb, vs2)
    if len(db.all_chunks()) > 0 and vs2.count() == 0:
        ing2.rebuild_all()
    assert vs2.count() == 1
    res = vs2.search(emb.embed(["内容A"])[0], k=5)
    assert res and res[0][0].startswith("A##")
