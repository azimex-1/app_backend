import uuid

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_permission
from app.core.security import create_access_token, hash_password, verify_password
from app.schemas.password import ChangePasswordRequest, ResetPasswordRequest
from app.core.utils import slugify
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.schemas.token import Token
from app.schemas.user import UserRead

router = APIRouter()


async def _unique_slug(db: DbSession, base: str) -> str:
    slug = slugify(base)
    candidate = slug
    suffix = 1
    while await db.scalar(select(Organization.id).where(Organization.slug == candidate)):
        suffix += 1
        candidate = f"{slug}-{suffix}"
    return candidate


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DbSession) -> Token:
    """Bootstrap a new organization and its owner user."""
    existing = await db.scalar(select(User.id).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    org = Organization(
        name=payload.organization_name,
        slug=await _unique_slug(db, payload.organization_name),
    )
    db.add(org)
    await db.flush()

    user = User(
        organization_id=org.id,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        is_owner=True,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return Token(access_token=create_access_token(user.id))


@router.post("/login", response_model=Token)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> Token:
    user = await db.scalar(select(User).where(User.email == form.username))
    if not user or not verify_password(form.password, user.hashed_password) or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserRead)
async def read_me(user: CurrentUser) -> User:
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_my_password(
    payload: ChangePasswordRequest,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """The logged-in user changes their own password (must prove the current one)."""
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    await db.commit()


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_user_password(
    user_id: uuid.UUID,
    payload: ResetPasswordRequest,
    db: DbSession,
    current: Annotated[User, Depends(require_permission("user.manage"))],
) -> None:
    """An admin/owner sets a new password for another user in their org."""
    target = await db.scalar(select(User).where(User.id == user_id))
    if target is None or target.organization_id != current.organization_id:
        raise HTTPException(status_code=404, detail="User not found")
    target.hashed_password = hash_password(payload.new_password)
    await db.commit()