import tempfile
from pathlib import Path

from app.core.config import Config
from app.core.db import Database
from app.core.embeddings import FakeEmbedder
from app.notes.store import NoteStore
from app.ingest.vector_store import VectorStore
from app.ingest.ingestor import Ingestor


def make_ingestor():
    d = tempfile.mkdtemp()
    cfg = Config(root_dir=Path(d), notes_dir=Path(d) / "notes", data_dir=Path(d) / "data")
    ns = NoteStore(cfg)
    db = Database(cfg.db_path); db.init()
    emb = FakeEmbedder(dim=8)
    vs = VectorStore(cfg, db, emb); vs.reset()
    return Ingestor(cfg, ns, db, emb, vs), ns, db


def test_index_and_rebuild():
    ing, ns, db = make_ingestor()
    ns.create("A", "# 标题\n内容")
    n = ing.index_note("A")
    assert n >= 1
    assert len(db.all_chunks()) >= 1
    stats = ing.rebuild_all()
    assert stats["notes"] == 1 and stats["chunks"] >= 1
    assert db.all_chunks()[0].note_id == "A"


def test_remove_note_clears_index():
    ing, ns, db = make_ingestor()
    ns.create("A", "# 标题\n内容")
    ing.index_note("A")
    assert len(db.all_chunks()) >= 1
    ing.remove_note("A")
    assert db.all_chunks() == []
    # Ruling 7: 删除后向量索引也必须清空，避免 search 返回已删除分块
    assert ing.vs.count() == 0


def test_rebuild_clears_stale_maps():
    ing, ns, db = make_ingestor()
    ns.create("A", "# 标题\n内容")
    ing.index_note("A")
    # 模拟历史遗留的孤立 faiss_map 行（Task 6 延后处理的 load() 不一致）
    ing.db._conn.execute("INSERT INTO faiss_map (faiss_id, chunk_id) VALUES (999, 'stale')")
    ing.db._conn.commit()
    ing.rebuild_all()
    # Ruling 7: 全量重建必须清掉遗留 faiss_map，重建后的映射只来自当前分块
    assert 999 not in ing.db.faiss_mapping()
    assert all(cid.startswith("A##") for cid in ing.db.faiss_mapping().values())
    assert [c.note_id for c in ing.db.all_chunks()] == ["A"]
