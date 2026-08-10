"""Throwaway test endpoints — NO auth, NO database, in-memory only.
Just to confirm the Flutter app and the backend can talk. Data resets when
the server restarts. We replace this with the real branch endpoints later.
"""
from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter()


class BranchIn(BaseModel):
    name: str
    code: str


class BranchOut(BranchIn):
    id: int


_branches: list[BranchOut] = []
_next_id: int = 1


@router.get("/branches", response_model=list[BranchOut])
async def list_branches() -> list[BranchOut]:
    return _branches


@router.post("/branches", response_model=BranchOut, status_code=status.HTTP_201_CREATED)
async def add_branch(payload: BranchIn) -> BranchOut:
    global _next_id
    branch = BranchOut(id=_next_id, name=payload.name, code=payload.code)
    _branches.append(branch)
    _next_id += 1
    return branch