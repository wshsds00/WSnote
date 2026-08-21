import re
from dataclasses import dataclass

from app.notes.models import Note

_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Chunk:
    chunk_id: str
    note_id: str
    heading_path: str
    text: str
    seq: int


def _split_blocks(markdown: str) -> list[tuple[str, str]]:
    """返回 [(heading_path, text)]，按 # 标题分段。"""
    matches = list(_HEADING.finditer(markdown))
    if not matches:
        return [("", markdown)] if markdown.strip() else []
    blocks: list[tuple[str, str]] = []
    heads: list[str] = []
    for i, m in enumerate(matches):
        # 用当前到下一个标题之间的文本
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        text = markdown[start:end].strip()
        if not text:
            continue
        heads.append(m.group(2).strip())
        blocks.append((" ## ".join(h for h in heads if h), text))
    if not blocks:
        stripped = markdown.strip()
        return [("", stripped)] if stripped else []
    return blocks


def _char_chunks(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    out = []
    i = 0
    step = max(1, size - overlap)
    while i < len(text):
        out.append(text[i:i + size])
        i += step
    return out


def split_note(note: Note, chunk_size: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    seq = 0
    for heading_path, text in _split_blocks(note.content):
        for piece in _char_chunks(text, chunk_size, overlap):
            path = heading_path if heading_path else note.title
            chunk_id = f"{note.id}##{path}##{seq}"
            chunks.append(Chunk(chunk_id=chunk_id, note_id=note.id,
                                heading_path=path, text=piece, seq=seq))
            seq += 1
    return chunks
