from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("")
def tags(request: Request):
    s = request.app.state.s
    counts: dict[str, int] = {}
    for m in s.note_store.list_notes():
        for t in m.tags:
            counts[t] = counts.get(t, 0) + 1
    return {"code": 0, "data": counts}
