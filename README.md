# fm-evidence-service

> **Part of [FaultMaven](https://github.com/FaultMaven/faultmaven)** —
> The AI-Powered Troubleshooting Copilot

**FaultMaven Evidence Management Microservice** - Open source file upload and storage for troubleshooting artifacts.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com/r/faultmaven/fm-evidence-service)

## Overview

The Evidence Service manages file uploads for troubleshooting cases in FaultMaven. Users can upload logs, screenshots, configuration files, and other diagnostic artifacts. Files are stored locally with metadata tracked in SQLite.

**Features:**
- **File Upload**: Multipart form-data upload with streaming
- **File Download**: Streaming downloads for large files
- **Metadata Tracking**: SQLite database for file metadata
- **Local Storage**: Filesystem-based storage with user/case isolation
- **Case Linking**: Associate evidence files with troubleshooting cases
- **User Isolation**: Each user only accesses their own files
- **File Validation**: Type and size restrictions
- **Persistent Storage**: Files persist in mounted volumes

## Quick Start

### Using Docker (Recommended)

```bash
# Run with persistent storage
docker run -d -p 8005:8005 \
  -v ./data/uploads:/data/uploads \
  faultmaven/fm-evidence-service:latest
```

The service will be available at `http://localhost:8005`.

### Using Docker Compose

See [faultmaven-deploy](https://github.com/FaultMaven/faultmaven-deploy) for complete deployment with all FaultMaven services.

### Development Setup

```bash
# Clone repository
git clone https://github.com/FaultMaven/fm-evidence-service.git
cd fm-evidence-service

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Run service
uvicorn evidence_service.main:app --reload --port 8005
```

## API Endpoints

### Evidence Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/evidence` | Upload evidence file |
| GET | `/api/v1/evidence/{evidence_id}` | Get evidence metadata |
| GET | `/api/v1/evidence/{evidence_id}/download` | Download evidence file |
| DELETE | `/api/v1/evidence/{evidence_id}` | Delete evidence |
| GET | `/api/v1/evidence` | List user's evidence (paginated) |
| GET | `/api/v1/evidence/case/{case_id}` | Get evidence for case |
| POST | `/api/v1/evidence/{evidence_id}/link` | Link evidence to case |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |

## Configuration

Configuration via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `SERVICE_NAME` | Service identifier | `fm-evidence-service` |
| `ENVIRONMENT` | Deployment environment | `development` |
| `PORT` | Service port | `8005` |
| `DATABASE_URL` | SQLite connection string | `sqlite+aiosqlite:////data/uploads/fm_evidence.db` |
| `UPLOAD_DIR` | File storage directory | `/data/uploads` |
| `MAX_FILE_SIZE_MB` | Maximum file size | `50` |
| `ALLOWED_EXTENSIONS` | Allowed file types | `.txt,.log,.json,.yaml,.yml,.xml,.csv,.pdf,.png,.jpg,.jpeg` |
| `LOG_LEVEL` | Logging level | `INFO` |

## File Upload

Upload files via multipart/form-data:

```bash
curl -X POST http://localhost:8005/api/v1/evidence \
  -H "X-User-ID: user_123" \
  -F "file=@application.log" \
  -F "case_id=case_abc123" \
  -F "evidence_type=log" \
  -F "description=Application error log from production"
```

Response:
```json
{
    "evidence_id": "evid_xyz789",
    "user_id": "user_123",
    "case_id": "case_abc123",
    "filename": "application.log",
    "file_type": "log",
    "file_size": 1048576,
    "evidence_type": "log",
    "description": "Application error log from production",
    "storage_path": "/data/uploads/user_123/case_abc123/evid_xyz789_application.log",
    "uploaded_at": "2025-11-16T10:30:00Z",
    "uploaded_by": "user_123"
}
```

## File Download

Download files with streaming:

```bash
curl -X GET http://localhost:8005/api/v1/evidence/evid_xyz789/download \
  -H "X-User-ID: user_123" \
  -o application.log
```

## Evidence Types

Supported evidence types for categorization:

- `log` - Application/system logs
- `screenshot` - Screen captures
- `config` - Configuration files
- `metric` - Performance metrics
- `document` - Documentation files
- `other` - Uncategorized files

## Data Model

### Evidence Metadata (SQLite)

```python
{
    "evidence_id": str,        # Unique identifier
    "user_id": str,            # Owner user ID
    "case_id": str,            # Associated case (optional)
    "filename": str,           # Original filename
    "file_type": str,          # File extension
    "file_size": int,          # Size in bytes
    "storage_path": str,       # Local filesystem path
    "evidence_type": str,      # Category (log/screenshot/config/etc)
    "description": str,        # Optional description
    "metadata": dict,          # Additional metadata
    "uploaded_at": datetime,   # Upload timestamp
    "uploaded_by": str         # Uploader user ID
}
```

## Storage Structure

Files are organized by user and case:

```
/data/uploads/
├── {user_id}/
│   ├── {case_id}/
│   │   ├── {evidence_id}_{filename}
│   │   └── {evidence_id}_{filename}
│   └── unlinked/
│       └── {evidence_id}_{filename}
└── fm_evidence.db (SQLite metadata)
```

## Authorization

This service uses **trusted header authentication** from the FaultMaven API Gateway:

- `X-User-ID` (required): Identifies the user making the request
- `X-User-Email` (optional): User's email address
- `X-User-Roles` (optional): User's roles

All evidence operations are scoped to the user specified in `X-User-ID`. Users can only access their own files.

**Important**: This service should run behind the [fm-api-gateway](https://github.com/FaultMaven/faultmaven) which handles authentication and sets these headers. Never expose this service directly to the internet.

## Architecture

```
┌─────────────────┐
│  API Gateway    │ (Handles authentication)
└────────┬────────┘
         │ X-User-ID header
         ↓
┌─────────────────┐
│ Evidence Svc    │ (File processing)
└────┬───────┬────┘
     │       │
     ↓       ↓
┌─────────┐ ┌──────────────┐
│ SQLite  │ │  Local FS    │
│Metadata │ │ File Storage │
└─────────┘ └──────────────┘
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=evidence_service

# Run specific test file
pytest tests/test_evidence.py -v
```

## Related Projects

- [faultmaven](https://github.com/FaultMaven/faultmaven) - Main backend with API Gateway
- [faultmaven-copilot](https://github.com/FaultMaven/faultmaven-copilot) - Browser extension UI
- [faultmaven-deploy](https://github.com/FaultMaven/faultmaven-deploy) - Docker Compose deployment

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

## Contributing

See our [Contributing Guide](https://github.com/FaultMaven/.github/blob/main/CONTRIBUTING.md) for detailed guidelines.

## Support

- **Discussions:** [GitHub Discussions](https://github.com/FaultMaven/faultmaven/discussions)
- **Issues:** [GitHub Issues](https://github.com/FaultMaven/fm-evidence-service/issues)
