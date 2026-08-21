from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/notes", tags=["notes"])


class NoteIn(BaseModel):
    title: str
    content: str = ""
    tags: list[str] = []


def _resp(data):
    return {"code": 0, "data": data}


@router.get("")
def list_notes(request: Request):
    s = request.app.state.s
    return _resp([m.__dict__ for m in s.note_store.list_notes()])


@router.post("")
def create_note(body: NoteIn, request: Request):
    s = request.app.state.s
    note = s.note_store.create(body.title, body.content, body.tags)
    s.ingestor.index_note(note.id)
    return _resp(note.__dict__)


@router.get("/{note_id}")
def get_note(note_id: str, request: Request):
    s = request.app.state.s
    note = s.note_store.read(note_id)
    if note is None:
        raise HTTPException(404, "note not found")
    return _resp(note.__dict__)


@router.put("/{note_id}")
def update_note(note_id: str, body: NoteIn, request: Request):
    s = request.app.state.s
    if s.note_store.read(note_id) is None:
        raise HTTPException(404, "note not found")
    note = s.note_store.update(note_id, body.content, body.tags)
    s.ingestor.index_note(note_id)
    return _resp(note.__dict__)


@router.delete("/{note_id}")
def delete_note(note_id: str, request: Request):
    s = request.app.state.s
    s.ingestor.remove_note(note_id)
    s.note_store.delete(note_id)
    return _resp({"ok": True})
