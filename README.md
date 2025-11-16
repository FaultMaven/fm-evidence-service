# FM Evidence Service

Microservice for managing evidence files (logs, screenshots, documents, metrics) for FaultMaven troubleshooting cases.

## Features

- File upload with multipart/form-data
- File download with streaming
- File metadata storage in SQLite/PostgreSQL
- Local filesystem storage (development)
- S3/MinIO storage support (production, stub)
- Evidence-case linking
- User-scoped evidence access
- Pagination and filtering
- File type validation
- File size limits
- Health checks

## Architecture

```
fm-evidence-service/
├── src/evidence_service/
│   ├── api/routes/          # FastAPI endpoints
│   ├── core/                # Business logic
│   ├── infrastructure/      # Database & storage
│   ├── models/              # Data models
│   ├── config/              # Configuration
│   └── main.py              # FastAPI app
├── uploads/                 # Local file storage
├── tests/                   # Test suite
└── pyproject.toml           # Dependencies
```

## Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Create uploads directory
mkdir -p uploads

# Copy environment template
cp .env.example .env
```

## Running the Service

```bash
# Development mode (with auto-reload)
python -m evidence_service.main

# Or with uvicorn directly
uvicorn evidence_service.main:app --reload --host 0.0.0.0 --port 8004
```

The service will be available at: http://localhost:8004

## API Endpoints

### Evidence Management

- `POST /api/v1/evidence` - Upload evidence file
- `GET /api/v1/evidence/{evidence_id}` - Get evidence metadata
- `GET /api/v1/evidence/{evidence_id}/download` - Download evidence file
- `DELETE /api/v1/evidence/{evidence_id}` - Delete evidence
- `GET /api/v1/evidence` - List user's evidence (paginated)
- `GET /api/v1/evidence/case/{case_id}` - Get evidence for case
- `POST /api/v1/evidence/{evidence_id}/link` - Link evidence to case

### Health

- `GET /health` - Health check (root level)
- `GET /api/v1/evidence/health` - Detailed health check

## Authentication

This service trusts the `X-User-ID` header from the API gateway. No JWT validation is needed.

All requests must include:
```
X-User-ID: user-123
```

## Configuration

Environment variables (see `.env.example`):

- `PORT` - Service port (default: 8004)
- `DATABASE_URL` - Database connection URL
- `STORAGE_TYPE` - Storage backend (local or s3)
- `MAX_FILE_SIZE_MB` - Maximum file size (default: 50MB)
- `ALLOWED_FILE_TYPES` - Comma-separated file extensions

## Storage

### Development (Local)

Files are stored in `./uploads/{user_id}/{case_id}/{evidence_id}_{filename}`

### Production (S3/MinIO)

Configure S3 settings in `.env`:
```
STORAGE_TYPE=s3
S3_ENDPOINT_URL=http://minio:9000
S3_BUCKET_NAME=faultmaven-evidence
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
```

Note: S3 storage is currently a stub and will be implemented when deploying to Kubernetes.

## Database Schema

Evidence metadata table:
```sql
CREATE TABLE evidence (
    evidence_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    case_id VARCHAR(100),
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(100) NOT NULL,
    file_size INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    evidence_type VARCHAR(50) NOT NULL,
    description TEXT,
    metadata JSON,
    uploaded_at TIMESTAMP NOT NULL,
    uploaded_by VARCHAR(100) NOT NULL
);
```

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=evidence_service --cov-report=html
```

## Integration with Other Services

This service is part of the FaultMaven microservices architecture:

- **fm-auth-service** (port 8001) - JWT authentication
- **fm-api-gateway** (port 8090) - API gateway, adds X-User-* headers
- **fm-session-service** (port 8002) - Session management
- **fm-case-service** (port 8003) - Case management
- **fm-evidence-service** (port 8004) - Evidence management (this service)

## Development Notes

- Uses async/await throughout
- SQLAlchemy 2.0 with async support
- Pydantic v2 for data validation
- FastAPI dependency injection
- File streaming for downloads
- Proper error handling and logging
