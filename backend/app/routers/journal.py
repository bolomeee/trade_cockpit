from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_journal_service
from app.schemas.journal import (
    JournalDeleteOut,
    JournalEntryCreate,
    JournalEntryOut,
    JournalEntryUpdate,
    JournalListOut,
)
from app.schemas.watchlist import ResponseEnvelope
from app.services.journal_service import JournalService

router = APIRouter(prefix="/api/journal", tags=["journal"])


@router.get("", response_model=ResponseEnvelope[JournalListOut])
def list_journal(
    ticker: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1),
    offset: int | None = Query(default=None, ge=0),
    service: JournalService = Depends(get_journal_service),
) -> ResponseEnvelope[JournalListOut]:
    data = service.list(ticker=ticker, action=action, limit=limit, offset=offset)
    return ResponseEnvelope(data=JournalListOut.model_validate(data))


@router.post(
    "",
    response_model=ResponseEnvelope[JournalEntryOut],
    status_code=status.HTTP_201_CREATED,
)
def create_journal(
    payload: JournalEntryCreate,
    service: JournalService = Depends(get_journal_service),
) -> ResponseEnvelope[JournalEntryOut]:
    data = service.create(payload.model_dump())
    return ResponseEnvelope(data=JournalEntryOut.model_validate(data))


@router.put("/{entry_id}", response_model=ResponseEnvelope[JournalEntryOut])
def update_journal(
    entry_id: int,
    payload: JournalEntryUpdate,
    service: JournalService = Depends(get_journal_service),
) -> ResponseEnvelope[JournalEntryOut]:
    data = service.update(entry_id, payload.model_dump(exclude_unset=True))
    return ResponseEnvelope(data=JournalEntryOut.model_validate(data))


@router.delete("/{entry_id}", response_model=ResponseEnvelope[JournalDeleteOut])
def delete_journal(
    entry_id: int,
    service: JournalService = Depends(get_journal_service),
) -> ResponseEnvelope[JournalDeleteOut]:
    removed_id = service.delete(entry_id)
    return ResponseEnvelope(data=JournalDeleteOut(id=removed_id, deleted=True))
