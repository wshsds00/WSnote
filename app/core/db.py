import sqlite3
from pathlib import Path

from app.ingest.chunker import Chunk

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    note_id TEXT NOT NULL,
    heading_path TEXT NOT NULL,
    text TEXT NOT NULL,
    seq INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS faiss_map (
    faiss_id INTEGER PRIMARY KEY,
    chunk_id TEXT UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS eval_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_json TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_note ON chunks(note_id);
"""


class Database:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row

    def init(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def insert_chunks(self, chunks: list[Chunk]) -> None:
        self._conn.executemany(
            "INSERT OR REPLACE INTO chunks (chunk_id, note_id, heading_path, text, seq) VALUES (?,?,?,?,?)",
            [(c.chunk_id, c.note_id, c.heading_path, c.text, c.seq) for c in chunks],
        )
        self._conn.commit()

    def delete_chunks_for_note(self, note_id: str) -> None:
        rows = self._conn.execute("SELECT chunk_id FROM chunks WHERE note_id=?", (note_id,)).fetchall()
        self.delete_faiss_maps([r["chunk_id"] for r in rows])
        self._conn.execute("DELETE FROM chunks WHERE note_id=?", (note_id,))
        self._conn.commit()

    def all_chunks(self) -> list[Chunk]:
        rows = self._conn.execute("SELECT * FROM chunks ORDER BY note_id, seq").fetchall()
        return [Chunk(chunk_id=r["chunk_id"], note_id=r["note_id"],
                      heading_path=r["heading_path"], text=r["text"], seq=r["seq"]) for r in rows]

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        r = self._conn.execute("SELECT * FROM chunks WHERE chunk_id=?", (chunk_id,)).fetchone()
        if r is None:
            return None
        return Chunk(chunk_id=r["chunk_id"], note_id=r["note_id"],
                     heading_path=r["heading_path"], text=r["text"], seq=r["seq"])

    def upsert_faiss_map(self, faiss_id: int, chunk_id: str) -> None:
        self._conn.execute("INSERT OR REPLACE INTO faiss_map (faiss_id, chunk_id) VALUES (?,?)", (faiss_id, chunk_id))
        if faiss_id >= self.next_faiss_id():
            self._conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('next_faiss_id', ?)",
                (str(faiss_id + 1),),
            )
        self._conn.commit()

    def delete_faiss_maps(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        marks = ",".join("?" for _ in chunk_ids)
        self._conn.execute(f"DELETE FROM faiss_map WHERE chunk_id IN ({marks})", chunk_ids)
        self._conn.commit()

    def faiss_mapping(self) -> dict[int, str]:
        rows = self._conn.execute("SELECT faiss_id, chunk_id FROM faiss_map").fetchall()
        return {r["faiss_id"]: r["chunk_id"] for r in rows}

    def next_faiss_id(self) -> int:
        r = self._conn.execute("SELECT value FROM meta WHERE key='next_faiss_id'").fetchone()
        return int(r["value"]) if r else 1

    def set_next_faiss_id(self, value: int) -> None:
        self._conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('next_faiss_id', ?)", (str(value),))
        self._conn.commit()

    def record_eval_run(self, config_json: str, metrics_json: str) -> None:
        import datetime
        self._conn.execute(
            "INSERT INTO eval_runs (config_json, metrics_json, created_at) VALUES (?,?,?)",
            (config_json, metrics_json, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        self._conn.commit()

    def get_tag_counts(self) -> dict[str, int]:
        return {}
