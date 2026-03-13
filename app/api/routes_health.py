from fastapi import APIRouter
from app.models.schemas import HealthResponse
from app.db.database import get_db
from app.services.resolver_service import fuzzy_index_size

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        get_db().execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        db_connected=db_ok,
        fuzzy_index_size=fuzzy_index_size(),
    )
