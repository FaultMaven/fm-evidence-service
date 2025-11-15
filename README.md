# FM Evidence Service

FaultMaven microservice for evidence service.

## Overview

Manages evidence service functionality for FaultMaven.

## API Endpoints

See `src/evidence_service/api/routes/` for implementation details.

## Local Development

### Prerequisites

- Python 3.11+
- Poetry
- Docker & Docker Compose

### Setup

```bash
# Install dependencies
poetry install

# Start infrastructure
docker-compose up -d postgres redis

# Run migrations (if applicable)
poetry run alembic upgrade head

# Start service
poetry run uvicorn src.evidence_service.main:app --reload
```

### Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src --cov-report=html

# Run specific test types
poetry run pytest tests/unit/
poetry run pytest tests/integration/
poetry run pytest tests/contract/
```

## Docker Deployment

```bash
# Build image
docker-compose build

# Run full stack
docker-compose up

# Access service
curl http://localhost:8003/health
```

## Environment Variables

See `.env.example` for required configuration.

## Database Schema

See `SERVICE_EXTRACTION_MAP.md` for database table details.

## Events Published

See `SERVICE_EXTRACTION_MAP.md` for event specifications.

## Events Consumed

See `SERVICE_EXTRACTION_MAP.md` for event subscriptions.
