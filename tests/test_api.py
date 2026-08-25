import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import create_app
from app.core.config import Config
from app.core.db import Database
from app.core.embeddings import FakeEmbedder
from app.core.llm import FakeLLM
from app.notes.store import NoteStore
from app.ingest.vector_store import VectorStore
from app.ingest.ingestor import Ingestor


def make_client():
    d = tempfile.mkdtemp()
    cfg = Config(root_dir=Path(d), notes_dir=Path(d) / "notes", data_dir=Path(d) / "data")
    cfg.embedding_model = "__missing_model__"
    ns = NoteStore(cfg)
    db = Database(cfg.db_path); db.init()
    emb = FakeEmbedder(dim=8)
    vs = VectorStore(cfg, db, emb); vs.reset()
    ing = Ingestor(cfg, ns, db, emb, vs)
    app = create_app(cfg, ns, db, ing, FakeLLM())
    return TestClient(app)


def test_note_crud_and_search_and_chat():
    c = make_client()
    r = c.post("/api/notes", json={"title": "JVM 内存", "content": "# 内存\n堆和栈 垃圾回收"})
    assert r.status_code == 200 and r.json()["data"]["id"] == "JVM-内存"
    c.post("/api/index/rebuild")
    s = c.get("/api/search", params={"q": "垃圾回收"})
    assert s.status_code == 200 and s.json()["data"]["hits"]
    ch = c.post("/api/chat", json={"question": "垃圾回收是什么"})
    assert ch.status_code == 200
    assert "degraded" in ch.json()["data"]
    tags = c.get("/api/tags")
    assert tags.status_code == 200


def _parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:"):].strip()))
    return events


def test_chat_stream_streams_with_llm():
    c = make_client()
    r = c.post("/api/chat/stream", json={"question": "垃圾回收是什么"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(r.text)
    metas = [e for e in events if e["type"] == "meta"]
    deltas = "".join(e["content"] for e in events if e["type"] == "delta")
    assert metas and metas[0]["degraded"] is False
    assert deltas.strip()
    assert events[-1]["type"] == "done"


def test_update_missing_note_404():
    c = make_client()
    r = c.put("/api/notes/missing", json={"title": "x", "content": "y"})
    assert r.status_code == 404


def test_create_duplicate_slug_409():
    c = make_client()
    r1 = c.post("/api/notes", json={"title": "JVM 内存", "content": "x"})
    assert r1.status_code == 200
    r2 = c.post("/api/notes", json={"title": "JVM 内存", "content": "y"})
    assert r2.status_code == 409


def test_put_omitting_tags_preserves_existing():
    c = make_client()
    r = c.post("/api/notes", json={"title": "带标签", "content": "x", "tags": ["JVM"]})
    note_id = r.json()["data"]["id"]
    u = c.put(f"/api/notes/{note_id}", json={"title": "带标签", "content": "y"})
    assert u.status_code == 200
    assert u.json()["data"]["tags"] == ["JVM"]
