from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware   # ← this import

from app import models  # noqa: F401
from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(title="Azimex Platform API", version="0.1.0")

# ← this block is what adds the missing header
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "environment": settings.ENVIRONMENT}


app.include_router(api_router, prefix="/api/v1")