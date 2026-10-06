"""Developer-defined permission catalog — the source of truth.

Each entry is (code, description). Codes are namespaced `module.action`.
Module-access codes (e.g. 'pos.access') gate whether a module shows in the
sidebar / is reachable; finer codes (e.g. 'pos.refund') gate specific actions.

Add a code here, then POST /permissions/seed (as owner/role.manage) to insert it.
Nothing else needs to change for the code to become grantable.
"""

PERMISSION_CATALOG: list[tuple[str, str]] = [
    # Point of Sale
    ("pos.access", "Open and use the POS"),
    ("pos.discount", "Apply discounts / edit price at the till"),
    ("pos.refund", "Process refunds"),
    ("pos.session.manage", "Open and close POS sessions"),
    ("pos.cash_movement", "Record cash in / cash out"),
    # Inventory / items
    ("inventory.view", "View items"),
    ("inventory.manage", "Add / edit items"),
    # Customers
    ("customers.view", "View customers"),
    ("customers.manage", "Add / edit customers"),
    # Reports
    ("reports.view", "View reports & reconciliation"),
    # Administration
    ("user.manage", "Manage users"),
    ("role.manage", "Manage roles & permissions"),
]