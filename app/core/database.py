import ssl
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Local Postgres needs no SSL; Supabase (and other hosted poolers) require it.
# We detect localhost and only enable SSL for remote hosts, so switching between
# local dev and Supabase is just a one-line change in .env.
_is_local = "localhost" in settings.DATABASE_URL or "127.0.0.1" in settings.DATABASE_URL

_connect_args: dict = {
    # Required for Supabase's pooler (pgbouncer/Supavisor); harmless locally.
    "statement_cache_size": 0,
}
if not _is_local:
    _connect_args["ssl"] = ssl.create_default_context()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession, autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
