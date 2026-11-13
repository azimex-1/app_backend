"""Reset a user's password directly in the database.

Run from the backend root (where your .env lives), e.g.:

    # 1) if you forgot which email you used, list all users first:
    python -m scripts.reset_password

    # 2) then reset it:
    python -m scripts.reset_password you@example.com "NewPassw0rd!"

Uses the app's own hash_password(), so the new password works with login.
"""
import asyncio
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User


async def main() -> None:
    args = sys.argv[1:]

    async with AsyncSessionLocal() as db:
        # No args: list every user's email so you can find your account.
        if not args:
            users = (await db.scalars(select(User))).all()
            if not users:
                print("No users exist yet.")
                return
            print("Users:")
            for u in users:
                flag = " (owner)" if getattr(u, "is_owner", False) else ""
                print(f"  - {u.email}{flag}")
            print("\nReset with: python -m scripts.reset_password <email> <new_password>")
            return

        if len(args) != 2:
            print('Usage: python -m scripts.reset_password <email> "<new_password>"')
            raise SystemExit(1)

        email, new_pw = args
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"No user found with email: {email}")
            print("Run with no arguments to list all emails.")
            raise SystemExit(1)

        user.hashed_password = hash_password(new_pw)
        await db.commit()
        print(f"Password reset for {email}. You can log in now.")


if __name__ == "__main__":
    asyncio.run(main())