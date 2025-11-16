# FaultMaven Evidence Service - PUBLIC Open Source Version
# Apache 2.0 License

FROM python:3.11-slim

WORKDIR /app

# Copy pyproject.toml
COPY pyproject.toml ./

# Install dependencies
RUN pip install --no-cache-dir -e .

# Copy source code
COPY src/ ./src/

# Create uploads directory for file storage
RUN mkdir -p /data/uploads && chmod -R 777 /data

# Set PYTHONPATH to include src directory
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Expose port
EXPOSE 8005

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8005/health', timeout=2)"

# Run service
CMD ["python", "-m", "uvicorn", "evidence_service.main:app", "--host", "0.0.0.0", "--port", "8005"]
