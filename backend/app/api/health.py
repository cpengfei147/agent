from fastapi import APIRouter

from app.storage.redis_client import get_redis
from app.storage.postgres_client import check_db_connection
from app.core.llm_client import get_llm_client

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    checks = {
        "api": "ok"
    }

    # Check Redis
    try:
        redis_client = await get_redis()
        if await redis_client.ping():
            checks["redis"] = "ok"
        else:
            checks["redis"] = "error"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    # Check PostgreSQL
    try:
        if await check_db_connection():
            checks["postgres"] = "ok"
        else:
            checks["postgres"] = "error"
    except Exception as e:
        checks["postgres"] = f"error: {str(e)}"

    # Overall status
    all_ok = all(v == "ok" for v in checks.values())

    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": checks
    }


@router.get("/health/llm")
async def llm_health_check():
    """LLM connection health check"""
    try:
        llm_client = get_llm_client()
        if await llm_client.check_connection():
            return {"status": "ok", "provider": "openai"}
        else:
            return {"status": "error", "message": "Connection failed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
