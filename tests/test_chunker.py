from app.ingest.chunker import split_note
from app.notes.models import Note


def test_split_by_headings_preserves_path():
    note = Note(id="n1", title="n1", content="# 内存模型\n堆和栈。\n## GC\n垃圾回收。\n后文。", created="", updated="")
    chunks = split_note(note, chunk_size=200, overlap=20)
    paths = [c.heading_path for c in chunks]
    assert "内存模型" in paths[0]
    assert "内存模型 ## GC" in paths[-1]
    assert all(c.chunk_id.startswith("n1##") for c in chunks)


def test_chunk_size_respected_without_headings():
    note = Note(id="n1", title="n1", content="字" * 500, created="", updated="")
    chunks = split_note(note, chunk_size=100, overlap=10)
    assert len(chunks) >= 5
    assert all(len(c.text) <= 100 for c in chunks)
    assert chunks[0].seq == 0 and chunks[1].seq == 1


def test_empty_and_small():
    assert split_note(Note(id="a", title="a", content="", created="", updated=""), 100, 10) == []
    one = split_note(Note(id="b", title="b", content="短", created="", updated=""), 100, 10)
    assert len(one) == 1 and one[0].text == "短"
