from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/index", tags=["index"])


@router.post("/rebuild")
def rebuild(request: Request):
    s = request.app.state.s
    return {"code": 0, "data": s.ingestor.rebuild_all()}


@router.get("/status")
def status(request: Request):
    s = request.app.state.s
    return {"code": 0, "data": s.ingestor.status()}
