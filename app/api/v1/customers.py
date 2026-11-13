import uuid

from fastapi import Depends, APIRouter, HTTPException, status
from sqlalchemy import or_, select

from app.api.deps import DbSession, require_permission
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate

router = APIRouter()


@router.get("", response_model=list[CustomerRead])
async def list_customers(
    db: DbSession,
    _=Depends(require_permission("customers.view")),
    q: str | None = None,
    customer_type: str | None = None,
    status: str | None = None,
    include_archived: bool = False,
) -> list[Customer]:
    stmt = select(Customer).order_by(Customer.name)
    if not include_archived:
        stmt = stmt.where(Customer.is_archived.is_(False))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Customer.name.ilike(like),
            Customer.phone.ilike(like),
            Customer.contact_person.ilike(like),
            Customer.tax_number.ilike(like),
        ))
    if customer_type:
        stmt = stmt.where(Customer.customer_type == customer_type)
    if status:
        stmt = stmt.where(Customer.status == status)
    result = await db.scalars(stmt)
    return list(result.all())


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
async def create_customer(payload: CustomerCreate, db: DbSession, _=Depends(require_permission("customers.manage"))) -> Customer:
    customer = Customer(**payload.model_dump())
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=CustomerRead)
async def get_customer(customer_id: uuid.UUID, db: DbSession, _=Depends(require_permission("customers.view"))) -> Customer:
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.put("/{customer_id}", response_model=CustomerRead)
async def update_customer(customer_id: uuid.UUID, payload: CustomerUpdate, db: DbSession, _=Depends(require_permission("customers.manage"))) -> Customer:
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    await db.commit()
    await db.refresh(customer)
    return customer