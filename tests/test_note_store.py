import tempfile
from pathlib import Path

import pytest

from app.core.config import Config
from app.notes.store import NoteStore


def make_store():
    d = tempfile.mkdtemp()
    cfg = Config(root_dir=Path(d), notes_dir=Path(d) / "notes", data_dir=Path(d) / "data")
    return NoteStore(cfg), cfg


def test_create_read_update_delete():
    store, _ = make_store()
    note = store.create("测试笔记", "# 标题\n正文")
    assert note.id == "测试笔记"
    assert note.content == "# 标题\n正文"
    got = store.read(note.id)
    assert got.title == "测试笔记"
    updated = store.update(note.id, "# 标题\n新正文")
    assert "新正文" in updated.content
    store.delete(note.id)
    assert store.read(note.id) is None


def test_list_and_iter_all():
    store, _ = make_store()
    store.create("A", "内容A")
    store.create("B", "内容B")
    metas = store.list_notes()
    assert len(metas) == 2
    assert {m.title for m in metas} == {"A", "B"}
    assert len(list(store.iter_all())) == 2


def test_frontmatter_roundtrip():
    store, _ = make_store()
    n = store.create("带标签", "# 标题\n正文", tags=["JVM", "面试"])
    reloaded = store.read(n.id)
    assert reloaded.tags == ["JVM", "面试"]


def test_create_slug_collision_raises():
    store, _ = make_store()
    store.create("Spring-Boot", "已有内容")
    with pytest.raises(FileExistsError):
        store.create("Spring Boot", "新内容")


def test_read_scalar_tag_coerced_to_list():
    store, _ = make_store()
    store.create("标量标签", "正文")
    # 手写 YAML 把 tags 写成标量，read 应把字符串规整为单元素列表
    (store._path("标量标签")).write_text(
        "---\ntitle: 标量标签\ntags: JVM\n---\n正文\n", encoding="utf-8")
    note = store.read("标量标签")
    assert note.tags == ["JVM"]
