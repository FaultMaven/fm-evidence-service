#!/usr/bin/env python3
"""Auto-generate README.md from OpenAPI specification.

This script reads the OpenAPI spec generated from FastAPI and creates
a comprehensive README with endpoint documentation, examples, and statistics.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Any


def load_openapi_spec() -> Dict[str, Any]:
    """Load OpenAPI spec from docs/api/openapi.json"""
    spec_path = Path(__file__).parent.parent / "docs" / "api" / "openapi.json"

    if not spec_path.exists():
        raise FileNotFoundError(
            f"OpenAPI spec not found at {spec_path}. "
            "Run the app to generate it first."
        )

    with open(spec_path, 'r') as f:
        return json.load(f)


def generate_endpoint_table(spec: Dict[str, Any]) -> str:
    """Generate markdown table of endpoints"""
    endpoints = []

    for path, methods in spec.get('paths', {}).items():
        for method, details in methods.items():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                # Extract summary or use path as fallback
                summary = details.get('summary', path)

                endpoints.append({
                    'method': method.upper(),
                    'path': path,
                    'summary': summary
                })

    # Sort endpoints: health first, then by path
    def sort_key(e):
        if e['path'] == '/health':
            return (0, '')
        return (1, e['path'])

    endpoints.sort(key=sort_key)

    # Build markdown table
    table = "| Method | Endpoint | Description |\n"
    table += "|--------|----------|-------------|\n"

    for endpoint in endpoints:
        table += f"| {endpoint['method']} | `{endpoint['path']}` | {endpoint['summary']} |\n"

    return table


def extract_response_codes(spec: Dict[str, Any]) -> Dict[str, Set[str]]:
    """Extract unique response codes and their descriptions across all endpoints"""
    response_info = {}

    for path, methods in spec.get('paths', {}).items():
        for method, details in methods.items():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                for code, response_details in details.get('responses', {}).items():
                    desc = response_details.get('description', 'No description')
                    if code not in response_info:
                        response_info[code] = set()
                    response_info[code].add(desc)

    return response_info


def generate_response_codes_section(spec: Dict[str, Any]) -> str:
    """Generate response codes documentation"""
    response_info = extract_response_codes(spec)

    if not response_info:
        return ""

    section = "\n## Common Response Codes\n\n"

    # Sort codes numerically
    for code in sorted(response_info.keys(), key=lambda x: int(x)):
        descriptions = list(response_info[code])
        section += f"- **{code}**: {descriptions[0]}\n"

    return section


def count_endpoints(spec: Dict[str, Any]) -> int:
    """Count total number of endpoints"""
    count = 0
    for path, methods in spec.get('paths', {}).items():
        for method in methods.keys():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                count += 1
    return count


def main():
    """Generate README.md from OpenAPI specification"""
    print("🚀 Generating README.md from OpenAPI specification...")

    # Load spec
    spec = load_openapi_spec()

    # Extract metadata
    info = spec.get('info', {})
    title = info.get('title', 'FM Evidence Service')
    version = info.get('version', '0.1.0')
    description = info.get('description', 'Microservice for managing evidence files')

    # Generate sections
    endpoint_table = generate_endpoint_table(spec)
    response_codes = generate_response_codes_section(spec)
    total_endpoints = count_endpoints(spec)
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    # Build README content
    readme_content = f"""# {title}

> **🤖 This README is auto-generated** from code on every commit.
> Last updated: **{timestamp}** | Total endpoints: **{total_endpoints}**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com/r/faultmaven/fm-evidence-service)
[![Auto-Docs](https://img.shields.io/badge/docs-auto--generated-success.svg)](.github/workflows/generate-docs.yml)

## Overview

**{description}** - Part of the FaultMaven troubleshooting platform.

The Evidence Service manages file uploads, storage, and retrieval of evidence artifacts (logs, screenshots, documents, metrics) for troubleshooting cases. It supports both local filesystem and AWS S3 storage backends.

**Key Features:**
- **Multi-format Support**: Upload logs, screenshots, documents, metrics, and custom files
- **Flexible Storage**: Local filesystem or AWS S3 backend (configurable)
- **Case Association**: Link evidence to specific cases from fm-case-service
- **File Type Detection**: Automatic evidence type classification
- **Secure Downloads**: Streaming file downloads with proper content types
- **Pagination**: Efficient list endpoints with filtering by case and evidence type
- **Metadata Tracking**: Track filename, size, type, uploader, and timestamps
- **Health Monitoring**: Storage and database health checks

## Quick Start

### Using Docker (Recommended)

```bash
docker run -p 8004:8004 -v ./evidence-data:/app/evidence faultmaven/fm-evidence-service:latest
```

The service will be available at `http://localhost:8004`. Evidence files persist in the `./evidence-data` directory.

### Using Docker Compose

See [faultmaven-deploy](https://github.com/FaultMaven/faultmaven-deploy) for complete deployment with all FaultMaven services.

### Development Setup

```bash
# Clone repository
git clone https://github.com/FaultMaven/fm-evidence-service.git
cd fm-evidence-service

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate

# Install dependencies
pip install -e .

# Run service
uvicorn evidence_service.main:app --reload --port 8004
```

The service creates a SQLite database at `./fm_evidence.db` and stores files in `./evidence/` on first run.

## API Endpoints

{endpoint_table}

**OpenAPI Documentation**: See [docs/api/openapi.json](docs/api/openapi.json) or [docs/api/openapi.yaml](docs/api/openapi.yaml) for complete API specification.
{response_codes}

## Configuration

Configuration via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `SERVICE_NAME` | Service identifier | `fm-evidence-service` |
| `ENVIRONMENT` | Deployment environment | `development` |
| `HOST` | Service host | `0.0.0.0` |
| `PORT` | Service port | `8004` |
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./fm_evidence.db` |
| `STORAGE_BACKEND` | Storage backend type | `local` |
| `LOCAL_STORAGE_PATH` | Local storage directory | `./evidence` |
| `AWS_REGION` | AWS region for S3 | `us-east-1` |
| `AWS_BUCKET_NAME` | S3 bucket name | `` |
| `MAX_FILE_SIZE` | Maximum file size (bytes) | `104857600` (100MB) |
| `MAX_PAGE_SIZE` | Maximum pagination size | `100` |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `*` |

Example `.env` file:

```env
ENVIRONMENT=production
PORT=8004
DATABASE_URL=sqlite+aiosqlite:///./data/fm_evidence.db
STORAGE_BACKEND=s3
AWS_REGION=us-east-1
AWS_BUCKET_NAME=faultmaven-evidence-prod
MAX_FILE_SIZE=209715200  # 200MB
CORS_ORIGINS=https://app.faultmaven.com,https://admin.faultmaven.com
```

## Evidence Data Model

Example Evidence Object:

```json
{{
    "evidence_id": "evidence_abc123def456",
    "case_id": "case_xyz789",
    "filename": "server-logs.txt",
    "file_type": "text/plain",
    "file_size": 15420,
    "evidence_type": "log",
    "storage_path": "evidence/user_123/case_xyz789/server-logs.txt",
    "uploaded_by": "user_123",
    "uploaded_at": "2025-11-15T14:32:00Z",
    "description": "Production server error logs from Nov 15"
}}
```

### Evidence Types
- `log` - Log files (*.log, *.txt)
- `screenshot` - Images (*.png, *.jpg, *.jpeg, *.gif)
- `document` - Documents (*.pdf, *.docx, *.xlsx, *.csv)
- `metric` - Metrics/monitoring data (*.json, *.csv)
- `other` - Other file types

### Storage Backends

**Local Storage**:
- Files stored in `LOCAL_STORAGE_PATH` directory
- Organized by user and case: `evidence/{{user_id}}/{{case_id}}/{{filename}}`
- Suitable for development and single-server deployments

**S3 Storage**:
- Files stored in AWS S3 bucket
- Same organizational structure as local storage
- Requires AWS credentials (via environment variables or IAM roles)
- Suitable for production and multi-server deployments

## Authorization

This service uses **trusted header authentication** from the FaultMaven API Gateway:

**Required Headers:**

- `X-User-ID` (required): Identifies the user making the request

**Optional Headers:**

- `X-User-Email`: User's email address
- `X-User-Roles`: User's roles (comma-separated)

Evidence is organized by user and linked to cases. Authorization is enforced through case ownership at the API Gateway level.

**Security Model:**

- ✅ User identification via X-User-ID header
- ✅ Evidence isolated by case ownership (validated at gateway)
- ✅ File type validation and size limits enforced
- ⚠️ Service trusts headers set by upstream gateway

**Important**: This service should run behind the [fm-api-gateway](https://github.com/FaultMaven/faultmaven) which handles authentication and sets these headers. Never expose this service directly to the internet.

## Architecture

```
┌─────────────────────────┐
│  FaultMaven API Gateway │  Handles authentication (Clerk)
│  (Port 8000)            │  Sets X-User-ID header
└───────────┬─────────────┘
            │ Trusted headers (X-User-ID)
            ↓
┌─────────────────────────┐
│  fm-evidence-service    │  Trusts gateway headers
│  (Port 8004)            │  Manages file storage
└─────┬──────────┬────────┘
      │          │ SQLAlchemy ORM
      │          ↓
      │     ┌─────────────────────────┐
      │     │  SQLite Database        │  fm_evidence.db
      │     │  (Metadata)             │  File metadata & tracking
      │     └─────────────────────────┘
      │ File operations
      ↓
┌─────────────────────────┐
│  Storage Backend        │  Local FS or AWS S3
│  (Configurable)         │  Actual file storage
└─────────────────────────┘
```

**Related Services:**
- fm-session-service (8001) - Investigation sessions
- fm-knowledge-service (8002) - Knowledge base
- fm-case-service (8003) - Case management

**Storage Details:**

- **Database**: SQLite with aiosqlite async driver (metadata only)
- **Location**: `./fm_evidence.db` (configurable via DATABASE_URL)
- **Files**: Local filesystem (`./evidence/`) or AWS S3 (configurable)
- **Schema**: Auto-created on startup via SQLAlchemy
- **Indexes**: Optimized for case_id and evidence_type lookups

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage report
pytest --cov=evidence_service --cov-report=html --cov-report=term

# Run specific test file
pytest tests/test_evidence.py -v

# Run with debug output
pytest -vv -s
```

**Test Coverage Goals:**

- Unit tests: Core business logic (EvidenceManager)
- Integration tests: Storage operations (local + S3)
- API tests: Endpoint behavior and validation
- Target coverage: >80%

## Development Workflow

```bash
# Format code with black
black src/ tests/

# Lint with flake8
flake8 src/ tests/

# Type check with mypy
mypy src/

# Run all quality checks
black src/ tests/ && flake8 src/ tests/ && mypy src/ && pytest
```

## Related Projects

- [faultmaven](https://github.com/FaultMaven/faultmaven) - Main backend with API Gateway and orchestration
- [faultmaven-copilot](https://github.com/FaultMaven/faultmaven-copilot) - Browser extension UI for troubleshooting
- [faultmaven-deploy](https://github.com/FaultMaven/faultmaven-deploy) - Docker Compose deployment configurations
- [fm-session-service](https://github.com/FaultMaven/fm-session-service) - Investigation session management
- [fm-knowledge-service](https://github.com/FaultMaven/fm-knowledge-service) - Knowledge base and recommendations
- [fm-case-service](https://github.com/FaultMaven/fm-case-service) - Case management

## CI/CD

This repository uses **GitHub Actions** for automated documentation generation:

**Trigger**: Every push to `main` or `develop` branches

**Process**:
1. Generate OpenAPI spec (JSON + YAML)
2. Validate documentation completeness (fails if endpoints lack descriptions)
3. Auto-generate this README from code
4. Create pull request with changes (if on main)

See [.github/workflows/generate-docs.yml](.github/workflows/generate-docs.yml) for implementation details.

**Documentation Guarantee**: This README is always in sync with the actual code. Any endpoint changes automatically trigger documentation updates.

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and quality checks (`pytest && black . && flake8`)
5. Commit with clear messages (`git commit -m 'feat: Add amazing feature'`)
6. Push to your fork (`git push origin feature/amazing-feature`)
7. Open a Pull Request

**Code Style**: Black formatting, flake8 linting, mypy type checking
**Commit Convention**: Conventional Commits (feat/fix/docs/refactor/test/chore)

---

**📊 Documentation Statistics**
- Total endpoints: {total_endpoints}
- Last generated: {timestamp}
- OpenAPI spec version: {version}
- Generator: scripts/generate_readme.py
- CI/CD: GitHub Actions

*This README is automatically updated on every commit to ensure zero documentation drift.*
"""

    # Write README
    readme_path = Path(__file__).parent.parent / "README.md"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print(f"✅ README.md generated successfully")
    print(f"   Location: {readme_path}")
    print(f"   Total endpoints documented: {total_endpoints}")
    print(f"   Timestamp: {timestamp}")


if __name__ == "__main__":
    main()
