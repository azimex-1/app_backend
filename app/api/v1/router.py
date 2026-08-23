from fastapi import APIRouter

from app.api.v1 import (
    auth,
    branches,
    demo,
    organizations,
    permissions,
    product_import,
    products,
    reference,
    receipts,
    roles,
    users,
    payment,
    customers,
    customer_ledger,
    currency_rate,
    saved_ticket,
    pos_session,
    refund
)

api_router = APIRouter()
api_router.include_router(demo.router, prefix="/demo", tags=["demo"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(product_import.router, prefix="/products/import", tags=["product-import"])
api_router.include_router(receipts.router, prefix="/receipts", tags=["receipts"])
api_router.include_router(reference.brands_router, prefix="/brands", tags=["brands"])
api_router.include_router(reference.categories_router, prefix="/categories", tags=["categories"])
api_router.include_router(reference.units_router, prefix="/units", tags=["units"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(branches.router, prefix="/branches", tags=["branches"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["permissions"])
api_router.include_router(payment.accounts_router, prefix="/payment_account", tags=["payment_acc"])
api_router.include_router(payment.payment_types_router, prefix="/payment_type", tags=["payment_type"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(customer_ledger.router, prefix="/customer_ledger", tags=["customer_ledger"])
api_router.include_router(currency_rate.router, prefix="/currency_rates", tags=["currency_rates"])
api_router.include_router(saved_ticket.router, prefix="/saved_tickets", tags=["saved_tickets"])
api_router.include_router(pos_session.router, prefix="/pos-sessions", tags=["pos-sessions"])
api_router.include_router(refund.router, prefix="/receipts", tags=["refunds"])