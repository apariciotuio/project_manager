import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.infrastructure.persistence.database import get_session_factory

logger = logging.getLogger(__name__)

router = APIRouter()


async def _check_db() -> str:
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        logger.exception("DB health check failed")
        return "error"


@router.get("/health")
async def health() -> JSONResponse:
    db_status = await _check_db()

    checks: dict[str, str] = {"db": db_status}
    all_ok = all(v == "ok" for v in checks.values())

    status_code = 200 if all_ok else 503
    overall = "ok" if all_ok else "degraded"

    return JSONResponse(
        status_code=status_code,
        content={"data": {"status": overall, "checks": checks}, "message": "health check"},
    )
