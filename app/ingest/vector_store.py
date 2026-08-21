import logging
import numpy as np

from app.core.config import Config
from app.core.db import Database

logger = logging.getLogger("wsnote.vector")

try:
    import faiss
    _HAS_FAISS = True
except Exception:  # pragma: no cover
    faiss = None
    _HAS_FAISS = False


class _NumpyIndex:
    def __init__(self, dim: int):
        self.dim = dim
        self.vectors: list[np.ndarray] = []
        self.ids: list[int] = []
        self._id_to_pos: dict[int, int] = {}

    def add(self, vectors: np.ndarray, ids: np.ndarray) -> None:
        for v, i in zip(vectors, ids):
            self.vectors.append(v)
            self._id_to_pos[int(i)] = len(self.vectors) - 1
            self.ids.append(int(i))

    def search(self, q: np.ndarray, k: int):
        if not self.vectors:
            return np.zeros((1, 0), dtype="float32"), np.zeros((1, 0), dtype="int64")
        q = np.asarray(q).reshape(-1)
        q = q / (np.linalg.norm(q) + 1e-9)
        sims = [float(np.dot(v, q)) for v in self.vectors]
        order = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)[:k]
        # 返回 (dists, ids)，与 faiss search 的 (D, I) 顺序一致
        return (np.array([[sims[i] for i in order]], dtype="float32"),
                np.array([self.ids[i] for i in order], dtype="int64").reshape(1, -1))

    def remove(self, ids: np.ndarray) -> None:
        to_remove = {int(i) for i in ids}
        keep = [(v, i) for v, i in zip(self.vectors, self.ids) if i not in to_remove]
        self.vectors = [v for v, _ in keep]
        self.ids = [i for _, i in keep]
        self._id_to_pos = {i: pos for pos, (_, i) in enumerate(keep)}

    def ntotal(self) -> int:
        return len(self.vectors)


class VectorStore:
    def __init__(self, config: Config, db: Database, embedder):
        self.config = config
        self.db = db
        self.embedder = embedder
        if _HAS_FAISS:
            self.index = faiss.IndexIDMap(faiss.IndexFlatIP(embedder.dim))
        else:
            logger.warning("faiss 不可用：使用 numpy 兜底索引")
            self.index = _NumpyIndex(embedder.dim)
        self._id_to_chunk: dict[int, str] = {}
        self._chunk_to_id: dict[str, int] = {}
        self._loaded = False

    # faiss 1.x 与 numpy 兜底的 API 差异集中在这里：
    # faiss 用 add_with_ids / remove_ids / ntotal(属性)，numpy 用 add / remove / ntotal()。
    def _index_add(self, vectors: np.ndarray, ids: np.ndarray) -> None:
        if _HAS_FAISS:
            self.index.add_with_ids(vectors, ids)
        else:
            self.index.add(vectors, ids)

    def _index_remove(self, ids: np.ndarray) -> None:
        if _HAS_FAISS:
            self.index.remove_ids(ids)
        else:
            self.index.remove(ids)

    def _index_ntotal(self) -> int:
        if _HAS_FAISS:
            return int(self.index.ntotal)
        return int(self.index.ntotal())

    def add(self, chunk_id: str, vector: list[float]) -> int:
        if not self._loaded:
            self._sync_from_db()
        vec = np.asarray([vector], dtype="float32")
        vec = vec / (np.linalg.norm(vec) + 1e-9)
        fid = self.db.next_faiss_id()
        self._index_add(vec, np.asarray([fid], dtype="int64"))
        self._id_to_chunk[fid] = chunk_id
        self._chunk_to_id[chunk_id] = fid
        self.db.upsert_faiss_map(fid, chunk_id)
        self.db.set_next_faiss_id(fid + 1)
        return fid

    def search(self, vector: list[float], k: int) -> list[tuple[str, float]]:
        if not self._loaded:
            self._sync_from_db()
        vec = np.asarray([vector], dtype="float32")
        vec = vec / (np.linalg.norm(vec) + 1e-9)
        dists, ids = self.index.search(vec, k)
        out = []
        for d, i in zip(dists[0], ids[0]):
            if int(i) < 0:
                continue
            out.append((self._id_to_chunk[int(i)], float(d)))
        return out

    def remove_chunks(self, chunk_ids: list[str]) -> None:
        if not self._loaded:
            self._sync_from_db()
        ids = [self._chunk_to_id[c] for c in chunk_ids if c in self._chunk_to_id]
        if ids:
            self._index_remove(np.asarray(ids, dtype="int64"))
            for i in ids:
                self._id_to_chunk.pop(i, None)
            self._chunk_to_id = {c: i for c, i in self._chunk_to_id.items() if i not in set(ids)}
        self.db.delete_faiss_maps(chunk_ids)

    def save(self) -> None:
        if _HAS_FAISS:
            faiss.write_index(self.index, str(self.config.faiss_path))
        else:  # numpy 兜底：把向量写进 faiss_map 之外的 json 快照
            import json
            payload = {"ids": self.index.ids, "vectors": [v.tolist() for v in self.index.vectors]}
            self.config.faiss_path.with_suffix(".np.json").write_text(json.dumps(payload), encoding="utf-8")

    def load(self) -> None:
        if _HAS_FAISS and self.config.faiss_path.exists():
            # read_index 已返回 IndexIDMap，无需再包一层（否则会因索引非空报错）
            self.index = faiss.read_index(str(self.config.faiss_path))
        elif not _HAS_FAISS:
            import json
            p = self.config.faiss_path.with_suffix(".np.json")
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                idx = _NumpyIndex(self.embedder.dim)
                idx.ids = list(data["ids"])
                idx.vectors = [np.asarray(v, dtype="float32") for v in data["vectors"]]
                idx._id_to_pos = {i: pos for pos, i in enumerate(idx.ids)}
                self.index = idx
        self._sync_from_db()
        self._loaded = True

    def reset(self) -> None:
        self.index = faiss.IndexIDMap(faiss.IndexFlatIP(self.embedder.dim)) if _HAS_FAISS else _NumpyIndex(self.embedder.dim)
        self._id_to_chunk = {}
        self._chunk_to_id = {}
        self.db.set_next_faiss_id(1)
        self._loaded = True

    def count(self) -> int:
        if not self._loaded:
            self._sync_from_db()
        return self._index_ntotal()

    def _sync_from_db(self) -> None:
        mapping = self.db.faiss_mapping()
        self._id_to_chunk = {fid: cid for fid, cid in mapping.items()}
        self._chunk_to_id = {cid: fid for fid, cid in mapping.items()}
        self._loaded = True
