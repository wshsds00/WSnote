import json

from fastapi.testclient import TestClient
from app.main import create_app
from app.core.config import Config
from app.core.db import Database
from app.core.embeddings import FakeEmbedder
from app.core.llm import FakeLLM, OpenAICompatLLM
from app.notes.store import NoteStore
from app.ingest.vector_store import VectorStore
from app.ingest.ingestor import Ingestor
from app.process.service import MAX_CHARS
import tempfile
from pathlib import Path


def make_client(llm=None):
    d = tempfile.mkdtemp()
    cfg = Config(root_dir=Path(d), notes_dir=Path(d) / "notes", data_dir=Path(d) / "data")
    cfg.embedding_model = "__missing_model__"
    ns = NoteStore(cfg)
    db = Database(cfg.db_path); db.init()
    emb = FakeEmbedder(dim=8)
    vs = VectorStore(cfg, db, emb); vs.reset()
    ing = Ingestor(cfg, ns, db, emb, vs)
    if llm is None:
        llm = FakeLLM()
    app = create_app(cfg, ns, db, ing, llm)
    return TestClient(app)


def test_import_single_creates_and_indexes():
    c = make_client()
    r = c.post("/api/process/import", json={"text": "JVM 内存\n堆和栈 垃圾回收", "mode": "single"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["created"]) == 1
    assert data["created"][0]["title"] == "JVM 内存"
    # 已进入索引
    c.post("/api/index/rebuild")
    s = c.get("/api/search", params={"q": "垃圾回收"})
    assert s.json()["data"]["hits"]


def test_import_split_h1():
    c = make_client()
    text = "开篇前言。\n# 第一章\n内容A。\n# 第二章\n内容B。"
    r = c.post("/api/process/import", json={"text": text, "mode": "split_h1"})
    assert r.status_code == 200
    created = r.json()["data"]["created"]
    titles = {n["title"] for n in created}
    assert titles == {"前言", "第一章", "第二章"}


def test_import_split_h1_no_heading_falls_back_single():
    c = make_client()
    r = c.post("/api/process/import", json={"text": "没有标题的正文内容。", "mode": "split_h1"})
    assert r.status_code == 200
    created = r.json()["data"]["created"]
    assert len(created) == 1
    assert created[0]["title"] == "没有标题的正文内容"


def test_import_duplicate_title_skipped():
    c = make_client()
    r1 = c.post("/api/process/import", json={"text": "重复标题\n内容A"})
    assert r1.status_code == 200
    r2 = c.post("/api/process/import", json={"text": "重复标题\n内容B"})
    assert r2.status_code == 200
    data = r2.json()["data"]
    assert len(data["created"]) == 0
    assert data["skipped"] == ["重复标题"]


def test_import_empty_text_400():
    c = make_client()
    r = c.post("/api/process/import", json={"text": "   ", "mode": "single"})
    assert r.status_code == 400


def _parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:"):].strip()))
    return events


def test_analyze_streams_with_llm():
    c = make_client(llm=FakeLLM())
    r = c.post("/api/process/analyze", json={"text": "面试官问了我一致性。", "mode": "interview"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(r.text)
    metas = [e for e in events if e["type"] == "meta"]
    deltas = "".join(e["content"] for e in events if e["type"] == "delta")
    assert metas and metas[0]["degraded"] is False and metas[0]["mode"] == "interview"
    assert deltas.strip()
    assert events[-1]["type"] == "done"


def test_analyze_stream_error_yields_error_event():
    class _BrokenLLM:
        def available(self):
            return True

        def complete_stream(self, messages):
            raise RuntimeError("boom")

    c = make_client(llm=_BrokenLLM())
    r = c.post("/api/process/analyze", json={"text": "面试官问了我一致性。", "mode": "interview"})
    assert r.status_code == 200
    events = _parse_sse(r.text)
    assert any(e["type"] == "error" for e in events)
    assert not any(e["type"] == "done" for e in events)


def test_analyze_no_llm_degraded():
    c = make_client(llm=OpenAICompatLLM("", "", "deepseek-chat"))
    r = c.post("/api/process/analyze", json={"text": "面试官问了我一致性。", "mode": "interview"})
    assert r.status_code == 200
    assert not r.headers["content-type"].startswith("text/event-stream")
    data = r.json()["data"]
    assert data["degraded"] is True
    assert data["markdown"] == ""
    assert "WSNOTE_LLM_API_KEY" in data["message"]


def test_analyze_too_long_400():
    c = make_client()
    r = c.post("/api/process/analyze", json={"text": "字" * (MAX_CHARS + 1), "mode": "general"})
    assert r.status_code == 400


def test_analyze_unknown_mode_400():
    c = make_client()
    r = c.post("/api/process/analyze", json={"text": "内容", "mode": "bogus"})
    assert r.status_code == 400


def test_chat_stream_no_llm_degraded_json():
    c = make_client(llm=OpenAICompatLLM("", "", "deepseek-chat"))
    r = c.post("/api/chat/stream", json={"question": "垃圾回收是什么"})
    assert r.status_code == 200
    assert not r.headers["content-type"].startswith("text/event-stream")
    data = r.json()["data"]
    assert data["degraded"] is True


def test_chat_stream_empty_question_400():
    c = make_client()
    r = c.post("/api/chat/stream", json={"question": "   "})
    assert r.status_code == 400
