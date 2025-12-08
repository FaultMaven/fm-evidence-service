# FaultMaven Evidence Service - PUBLIC Open Source Version
# Apache 2.0 License

FROM python:3.11-slim

WORKDIR /app

# Copy pyproject.toml and source code
COPY pyproject.toml ./
COPY src/ ./src/

# Copy Alembic migrations
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Install dependencies
RUN pip install --no-cache-dir -e .

# Create uploads directory for file storage
RUN mkdir -p /data/uploads && chmod -R 777 /data

# Set PYTHONPATH to include src directory
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=2)"

# Run migrations then start service
# Migrations are idempotent - safe to run on every startup
CMD ["sh", "-c", "alembic upgrade head && python -m uvicorn evidence_service.main:app --host 0.0.0.0 --port 8000"]
