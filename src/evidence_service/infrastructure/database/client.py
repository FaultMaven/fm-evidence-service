"""
Database Client

Async SQLAlchemy database connection and session management.
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from evidence_service.config.settings import settings
from evidence_service.infrastructure.database.models import Base

logger = logging.getLogger(__name__)


class DatabaseClient:
    """Database client for managing async connections"""

    def __init__(self):
        self.engine = None
        self.session_maker = None

    async def initialize(self):
        """Initialize database engine and create tables"""
        logger.info(f"Initializing database: {settings.database_url}")

        # Create async engine
        self.engine = create_async_engine(
            settings.database_url,
            echo=False,
            poolclass=NullPool if settings.database_url.startswith("sqlite") else None,
        )

        # Create session maker
        self.session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized successfully")

    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")

    def get_session(self) -> AsyncSession:
        """Get database session"""
        if not self.session_maker:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self.session_maker()

    async def health_check(self) -> bool:
        """Check database health"""
        try:
            async with self.get_session() as session:
                await session.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database client instance
db_client = DatabaseClient()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session"""
    async with db_client.get_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
