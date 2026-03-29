from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router


app = FastAPI(
    title="Paper Search Agent API",
    version="0.1.0",
    description="Independent backend API service for multi-source paper retrieval.",
)
app.include_router(router)

