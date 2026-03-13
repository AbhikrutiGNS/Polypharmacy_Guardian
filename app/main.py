"""
MediSafe Backend — FastAPI entry point.

Start:
  uvicorn app.main:app --reload --port 8000

Docs:
  http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_interaction import router as interaction_router
from app.api.routes_drug_info    import router as drug_info_router
from app.api.routes_health       import router as health_router
from app.services.resolver_service import build_fuzzy_index

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the fuzzy index once at startup — not on every request."""
    log.info("Building fuzzy resolver index...")
    n = build_fuzzy_index()
    log.info(f"MediSafe ready — {n:,} brand names indexed")
    yield
    log.info("MediSafe shutting down")


app = FastAPI(
    title="MediSafe API",
    description="Drug interaction checker and drug information service with agentic RAG fallback.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # tighten this for production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(interaction_router)
app.include_router(drug_info_router)
