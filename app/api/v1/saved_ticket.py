import uuid

from fastapi import Depends, APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession, require_permission
from app.models.saved_ticket import SavedTicket
from app.schemas.saved_ticket import SavedTicketCreate, SavedTicketDetail, SavedTicketSummary

router = APIRouter()


@router.post("", response_model=SavedTicketDetail, status_code=status.HTTP_201_CREATED)
async def create_ticket(payload: SavedTicketCreate, db: DbSession, _=Depends(require_permission("pos.access"))) -> SavedTicket:
    ticket = SavedTicket(
        name=payload.name.strip(),
        customer_id=payload.customer_id,
        customer_name=payload.customer_name,
        total_minor=payload.total_minor,
        lines=[line.model_dump() for line in payload.lines],
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.get("", response_model=list[SavedTicketSummary])
async def list_tickets(db: DbSession, _=Depends(require_permission("pos.access"))) -> list[SavedTicketSummary]:
    result = await db.scalars(select(SavedTicket).order_by(SavedTicket.created_at.desc()))
    tickets = result.all()
    return [
        SavedTicketSummary(
            id=t.id,
            name=t.name,
            customer_name=t.customer_name,
            total_minor=t.total_minor,
            item_count=sum(int(line.get("quantity", 0)) for line in (t.lines or [])),
            created_at=t.created_at,
        )
        for t in tickets
    ]


@router.get("/{ticket_id}", response_model=SavedTicketDetail)
async def get_ticket(ticket_id: uuid.UUID, db: DbSession, _=Depends(require_permission("pos.access"))) -> SavedTicket:
    ticket = await db.get(SavedTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Saved ticket not found")
    return ticket


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket(ticket_id: uuid.UUID, db: DbSession, _=Depends(require_permission("pos.access"))):
    ticket = await db.get(SavedTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Saved ticket not found")
    await db.delete(ticket)
    await db.commit()