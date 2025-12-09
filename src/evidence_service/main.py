"""
FM Evidence Service - Main Application

FastAPI application for evidence file management.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from evidence_service.config.settings import settings
from evidence_service.api.routes.evidence import router as evidence_router
from evidence_service.infrastructure.database.client import db_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info(f"Starting {settings.service_name} v{settings.environment}")
    logger.info(f"Database: {settings.database_url}")

    # Initialize database
    await db_client.initialize()

    yield

    # Shutdown
    logger.info("Shutting down Evidence Service")
    await db_client.close()


# Create FastAPI app
app = FastAPI(
    title="FM Evidence Service",
    description="Microservice for managing evidence files (logs, screenshots, documents, metrics)",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(evidence_router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.service_name,
        "version": "0.1.0",
        "status": "running",
        "environment": settings.environment
    }


# Health endpoint (simple version at root level)
@app.get("/health")
async def health():
    """Simple health check"""
    return {"status": "healthy", "service": settings.service_name}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "evidence_service.main:app",
        host=settings.host,
        port=settings.port,
        reload=True if settings.environment == "development" else False
    )
