import re
from datetime import datetime
from pathlib import Path
from typing import Iterator

import frontmatter

from app.core.config import Config
from app.notes.models import Note, NoteMeta

_SAFE = re.compile(r"[^\w一-鿿-]")


def _slug(title: str) -> str:
    s = _SAFE.sub("-", title).strip("-")
    return s or "untitled"


class NoteStore:
    def __init__(self, config: Config):
        self.dir = config.notes_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, note_id: str) -> Path:
        return self.dir / f"{note_id}.md"

    def list_notes(self) -> list[NoteMeta]:
        out = []
        for p in sorted(self.dir.glob("*.md")):
            n = self.read(p.stem)
            if n:
                out.append(NoteMeta(n.id, n.title, n.tags, n.created, n.updated))
        return out

    def create(self, title: str, content: str, tags: list[str] | None = None) -> Note:
        note_id = _slug(title)
        if self._path(note_id).exists():
            raise FileExistsError(note_id)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        note = Note(id=note_id, title=title, tags=tags or [], created=now, updated=now, content=content)
        self._write(note)
        return note

    def read(self, note_id: str) -> Note | None:
        p = self._path(note_id)
        if not p.exists():
            return None
        post = frontmatter.loads(p.read_text(encoding="utf-8"))
        tags = post.get("tags", []) or []
        if isinstance(tags, str):
            tags = [tags]
        return Note(
            id=note_id,
            title=str(post.get("title", note_id)),
            tags=list(tags),
            created=str(post.get("created", "")),
            updated=str(post.get("updated", "")),
            content=post.content,
        )

    def update(self, note_id: str, content: str, tags: list[str] | None = None) -> Note:
        note = self.read(note_id)
        if note is None:
            raise KeyError(note_id)
        note.content = content
        note.updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if tags is not None:
            note.tags = tags
        self._write(note)
        return note

    def delete(self, note_id: str) -> None:
        self._path(note_id).unlink(missing_ok=True)

    def iter_all(self) -> Iterator[Note]:
        for p in sorted(self.dir.glob("*.md")):
            n = self.read(p.stem)
            if n:
                yield n

    def _write(self, note: Note) -> None:
        post = frontmatter.Post(note.content, title=note.title, tags=note.tags,
                                created=note.created, updated=note.updated)
        self._path(note.id).write_text(frontmatter.dumps(post), encoding="utf-8")
