"""Seed the global permission catalog. Run once after migrations:

    python -m scripts.seed_permissions
"""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.permission import Permission

# Foundation permissions. Extend this list as new modules are added
# (e.g. "inventory.item.create", "sales.pos.operate").
PERMISSIONS: list[tuple[str, str]] = [
    ("organization.manage", "Edit organization settings"),
    ("branch.manage", "Create, edit and delete branches"),
    ("user.manage", "Create and manage users"),
    ("role.manage", "Create and manage roles and permissions"),
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        existing = set(
            (await db.scalars(select(Permission.code))).all()
        )
        created = 0
        for code, description in PERMISSIONS:
            if code not in existing:
                db.add(Permission(code=code, description=description))
                created += 1
        await db.commit()
        print(f"Seed complete. {created} new permission(s) added.")


if __name__ == "__main__":
    asyncio.run(main())
