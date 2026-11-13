from fastapi import APIRouter

from app.api.v1 import (
    auth,
    branches,
    organizations,
    permissions,
    product_import,
    products,
    currency_rate,
    saved_ticket,
    pos_session,
    refund,
    customer_ledger,
    customers,
    payment,
    reference,
    receipts,
    roles,
    users,
    locations,
    stock_count,
    stock_adjustment,
    stock_transfer,
    stock_ledger
)

api_router = APIRouter()
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(product_import.router, prefix="/products/import", tags=["product-import"])
api_router.include_router(receipts.router, prefix="/receipts", tags=["receipts"])
api_router.include_router(reference.brands_router, prefix="/brands", tags=["brands"])
api_router.include_router(reference.categories_router, prefix="/categories", tags=["categories"])
api_router.include_router(reference.units_router, prefix="/units", tags=["units"])
api_router.include_router(payment.payment_types_router, prefix="/payment-types", tags=["payment-types"])
api_router.include_router(payment.accounts_router, prefix="/payment-accounts", tags=["payment-accounts"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(customer_ledger.router, prefix="/customers", tags=["customer-ledger"])
api_router.include_router(currency_rate.router, prefix="/currency-rates", tags=["currency-rates"])
api_router.include_router(saved_ticket.router, prefix="/saved-tickets", tags=["saved-tickets"])
api_router.include_router(pos_session.router, prefix="/pos-sessions", tags=["pos-sessions"])
api_router.include_router(refund.router, prefix="/receipts", tags=["refunds"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(branches.router, prefix="/branches", tags=["branches"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["permissions"])
api_router.include_router(locations.router, prefix="/locations", tags=["locations"])
api_router.include_router(stock_count.router, prefix="/stock-counts", tags=["stock-count"])
api_router.include_router(stock_adjustment.router, prefix="/stock-adjustments", tags=["stock-adjustment"]) 
api_router.include_router(stock_transfer.router, prefix="/stock-transfers", tags=["stock-transfer"])# import block
api_router.include_router(stock_ledger.router, prefix="/stock-movements", tags=["stock-ledger"])