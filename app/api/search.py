from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def search(q: str, k: int = 5, rerank: bool = False, request: Request = None):
    s = request.app.state.s
    s.searcher.bm25.build(s.db.all_chunks())  # 保证 BM25 覆盖最新笔记
    hits = s.searcher.search(q, k=k, use_rerank=rerank)
    return {"code": 0, "data": {"hits": [h.__dict__ for h in hits]}}
