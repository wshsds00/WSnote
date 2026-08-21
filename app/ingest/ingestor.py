import logging

from app.core.config import Config
from app.core.db import Database
from app.ingest.chunker import split_note
from app.ingest.vector_store import VectorStore
from app.notes.store import NoteStore

logger = logging.getLogger("wsnote.ingest")


class Ingestor:
    def __init__(self, config: Config, note_store: NoteStore,
                 db: Database, embedder, vector_store: VectorStore):
        self.config = config
        self.notes = note_store
        self.db = db
        self.embedder = embedder
        self.vs = vector_store

    def index_note(self, note_id: str) -> int:
        note = self.notes.read(note_id)
        if note is None:
            return 0
        self.remove_note(note_id)
        chunks = split_note(note, self.config.chunk_size, self.config.chunk_overlap)
        if not chunks:
            return 0
        self.db.insert_chunks(chunks)
        texts = [c.text for c in chunks]
        vecs = self.embedder.embed(texts)
        for c, v in zip(chunks, vecs):
            self.vs.add(c.chunk_id, v)
        self.vs.save()
        return len(chunks)

    def remove_note(self, note_id: str) -> None:
        chunk_ids = [c.chunk_id for c in self.db.all_chunks() if c.note_id == note_id]
        self.vs.remove_chunks(chunk_ids)
        self.db.delete_chunks_for_note(note_id)
        self.vs.save()

    def rebuild_all(self) -> dict:
        self.vs.reset()
        self.db._conn.execute("DELETE FROM chunks")
        self.db._conn.execute("DELETE FROM faiss_map")
        self.db._conn.commit()
        total = 0
        for note in self.notes.iter_all():
            total += self.index_note(note.id)
        self.vs.save()
        return {"notes": len(self.notes.list_notes()), "chunks": total}

    def status(self) -> dict:
        return {"chunks": self.vs.count(), "notes": len(self.notes.list_notes())}
