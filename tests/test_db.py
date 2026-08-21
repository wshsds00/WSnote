from app.core.config import Config
from app.core.db import Database
from app.ingest.chunker import Chunk
import tempfile
from pathlib import Path


def make_db():
    d = tempfile.mkdtemp()
    cfg = Config(root_dir=Path(d), notes_dir=Path(d) / "notes", data_dir=Path(d) / "data")
    db = Database(cfg.db_path)
    db.init()
    return db


def test_chunk_roundtrip_and_delete():
    db = make_db()
    c = Chunk(chunk_id="n1##内存#0", note_id="n1", heading_path="内存", text="堆", seq=0)
    db.insert_chunks([c])
    assert db.get_chunk(c.chunk_id).text == "堆"
    db.delete_chunks_for_note("n1")
    assert db.get_chunk(c.chunk_id) is None


def test_faiss_map_and_next_id():
    db = make_db()
    db.upsert_faiss_map(1, "c1")
    db.upsert_faiss_map(2, "c2")
    assert db.faiss_mapping() == {1: "c1", 2: "c2"}
    assert db.next_faiss_id() == 3
    db.delete_faiss_maps(["c1"])
    assert db.faiss_mapping() == {2: "c2"}


def test_eval_runs_and_tags():
    db = make_db()
    db.record_eval_run('{"a":1}', '{"recall":0.5}')
    assert db.get_tag_counts() == {}
