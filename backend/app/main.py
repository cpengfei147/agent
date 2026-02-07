import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api import health_router, websocket_router, quotes_router, items_router
from app.storage.redis_client import get_redis, close_redis
from app.storage.postgres_client import init_db, close_db

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting ERABU Agent...")

    # Initialize Redis
    try:
        redis_client = await get_redis()
        if await redis_client.ping():
            logger.info("Redis connected")
        else:
            logger.warning("Redis connection failed")
    except Exception as e:
        logger.warning(f"Redis not available: {e}")

    # Initialize Database
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")

    logger.info("ERABU Agent started successfully")

    yield

    # Shutdown
    logger.info("Shutting down ERABU Agent...")
    await close_redis()
    await close_db()
    logger.info("ERABU Agent stopped")


# Create FastAPI app
app = FastAPI(
    title="ERABU Agent",
    description="Moving Service AI Assistant",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(websocket_router)
app.include_router(quotes_router)
app.include_router(items_router)

# Mount static files for frontend
try:
    app.mount("/static", StaticFiles(directory="frontend"), name="static")
except Exception:
    logger.warning("Frontend directory not found, static files not mounted")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "ERABU Agent",
        "version": "0.1.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.env == "development"
    )
