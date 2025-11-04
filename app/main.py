"""
Main FastAPI application
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.api.v1 import router as api_router
from app.middleware.error_handler import setup_exception_handlers
from app.db.session import init_db_pool, close_db_pool, get_db_connection
from app.db.models import init_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("🚀 Starting ContractMind Backend...")

    # Initialize database connection pool
    logger.info("📊 Initializing database connection pool...")
    init_db_pool()

    # Create tables
    logger.info("📊 Creating database tables...")
    with get_db_connection() as conn:
        init_database(conn)

    logger.info("✅ ContractMind Backend started successfully!")

    yield

    # Shutdown
    logger.info("🛑 Shutting down ContractMind Backend...")

    # Close database connections
    close_db_pool()

    logger.info("👋 ContractMind Backend stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="AI-powered blockchain infrastructure for natural language smart contract interactions",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add exception handlers
setup_exception_handlers(app)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "environment": settings.ENVIRONMENT, "version": "1.0.0"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "ContractMind Backend API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )
