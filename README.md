# Azimex Platform — Backend

FastAPI + async SQLAlchemy 2.0 + PostgreSQL. This is the **foundation layer**:
authentication, organizations, branches, users, and role-based access control.
Everything else (inventory, purchasing, sales, etc.) builds on these primitives.

## Architecture decisions

- **Async SQLAlchemy 2.0** with `asyncpg`.
- **UUID primary keys** everywhere.
- **Multi-tenancy:** every `Branch`, `User`, and `Role` belongs to an
  `Organization`. All queries are scoped to the caller's organization.
- **RBAC:** `User` ⇄ `Role` ⇄ `Permission`. The organization creator is an
  **owner** and bypasses permission checks (holds the `*` wildcard).
- **Auth:** JWT bearer tokens (PyJWT), bcrypt password hashing. Email is
  globally unique, so login is email + password.

## Layout

```
app/
  core/        config, database engine, security (hashing + JWT), utils
  models/      SQLAlchemy models + association tables
  schemas/     Pydantic v2 request/response models
  api/
    deps.py    get_current_user, require_permission(...)
    v1/        auth, organizations, branches, users, roles, permissions
  main.py      app entrypoint
alembic/       async migration environment
scripts/       seed_permissions.py
```

## Getting started

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then edit SECRET_KEY and DATABASE_URL
```

Make sure PostgreSQL is running and the database exists. Then:

```bash
# generate the first migration from the models, and apply it
alembic revision --autogenerate -m "foundation"
alembic upgrade head

# seed the permission catalog
python -m scripts.seed_permissions

# run the API
uvicorn app.main:app --reload
```

Interactive docs: http://localhost:8000/docs

## First requests

```bash
# 1. Bootstrap an organization + owner (returns a JWT)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"organization_name":"Azimex","full_name":"Owner","email":"owner@azimex.gm","password":"changeme123"}'

# 2. Log in (OAuth2 password form)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=owner@azimex.gm&password=changeme123"

# 3. Use the token
curl http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer <TOKEN>"
```

## What's stubbed / next

- No refresh tokens yet (access token only).
- Branch-scoped roles are not modelled yet — roles are org-wide, and
  `user_branches` only controls which branches a user can access.
- Permission catalog is seeded manually; module permissions get added as
  those modules are built.
