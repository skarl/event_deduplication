"""FastAPI application for Event Deduplication API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from event_dedup.api.routes.canonical_events import router as canonical_events_router
from event_dedup.api.routes.health import router as health_router

app = FastAPI(title="Event Deduplication API", version="0.1.0")

# CORS for Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(canonical_events_router)
