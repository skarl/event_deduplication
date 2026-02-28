"""FastAPI application skeleton for Event Deduplication API.

Minimal skeleton with /health endpoint. Phase 4 will add real routes.
"""

from fastapi import FastAPI

app = FastAPI(title="Event Deduplication API", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
