"""
Evidence API Routes

RESTful endpoints for evidence file management.
"""

import logging
import math
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Header,
    UploadFile,
    Query
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from io import BytesIO

from evidence_service.config.settings import settings
from evidence_service.core.evidence_manager import EvidenceManager
from evidence_service.infrastructure.database.client import get_db
from evidence_service.models import (
    EvidenceUploadResponse,
    EvidenceMetadataResponse,
    EvidenceListResponse,
    EvidenceListItem,
    LinkEvidenceToCaseRequest,
    HealthResponse,
    EvidenceType
)

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])
logger = logging.getLogger(__name__)

# Dependency for Evidence Manager
def get_evidence_manager() -> EvidenceManager:
    """Dependency for getting EvidenceManager instance"""
    return EvidenceManager()


@router.post(
    "",
    response_model=EvidenceUploadResponse,
    status_code=201,
    summary="Upload Evidence File",
    description="""
Upload an evidence file (log, screenshot, document, metric) and link it to a case.

**Workflow**:
1. Client sends multipart/form-data request with file and metadata
2. Service validates file size and type
3. Determines evidence type from file extension (log/screenshot/document/metric/other)
4. Stores file in configured backend (local filesystem or S3)
5. Creates metadata record in database
6. Returns evidence ID and metadata

**Request Format**:
- Content-Type: multipart/form-data
- file: File upload (required)
- case_id: Case ID to link evidence to (required)
- description: Optional description of the evidence

**File Type Detection**:
- Logs: .log, .txt
- Screenshots: .png, .jpg, .jpeg, .gif
- Documents: .pdf, .docx, .xlsx, .csv
- Metrics: .json (when containing metrics data)
- Other: All other file types

**Storage**:
Files are stored in `{{storage_backend}}/{{user_id}}/{{case_id}}/{{filename}}` where storage_backend is either local filesystem or S3.

**Authorization**: Requires X-User-ID header from API Gateway
**File Size Limit**: Configured via MAX_FILE_SIZE (default 100MB)
    """,
    responses={
        201: {"description": "Evidence uploaded successfully"},
        400: {"description": "File validation failed or case_id missing"},
        413: {"description": "File too large (exceeds MAX_FILE_SIZE)"},
        500: {"description": "Upload failed due to storage or database error"}
    }
)
async def upload_evidence(
    file: UploadFile = File(..., description="Evidence file to upload"),
    case_id: Optional[str] = Form(None, description="Case ID to link evidence to"),
    description: Optional[str] = Form(None, description="Evidence description"),
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
) -> EvidenceUploadResponse:
    """Upload evidence file"""
    try:
        # Read file content
        file_content = await file.read()

        # Validate case_id is provided
        if not case_id:
            raise HTTPException(status_code=400, detail="case_id is required")

        # Upload evidence
        evidence = await manager.upload_evidence(
            file_content=file_content,
            filename=file.filename,
            case_id=case_id,
            uploaded_by=x_user_id,
            description=description,
            db=db
        )

        logger.info(f"User {x_user_id} uploaded evidence: {evidence.evidence_id}")

        return EvidenceUploadResponse(
            evidence_id=evidence.evidence_id,
            filename=evidence.filename,
            file_type=evidence.file_type,
            file_size=evidence.file_size,
            evidence_type=evidence.evidence_type,
            uploaded_at=evidence.uploaded_at,
            message="Evidence uploaded successfully"
        )

    except ValueError as e:
        logger.warning(f"File validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Evidence upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get(
    "/{evidence_id}",
    response_model=EvidenceMetadataResponse,
    summary="Get Evidence Metadata",
    description="""
Retrieve metadata for a specific evidence file without downloading the actual file content.

**Workflow**:
1. Service looks up evidence record by ID in database
2. Returns metadata including filename, size, type, case association, and timestamps
3. Does not retrieve or stream actual file content (use /download for that)

**Response Fields**:
- evidence_id: Unique identifier
- case_id: Associated case ID
- filename: Original filename
- file_type: MIME type (e.g., "image/png", "text/plain")
- file_size: Size in bytes
- evidence_type: Classified type (log/screenshot/document/metric/other)
- uploaded_by: User ID of uploader
- uploaded_at: Upload timestamp
- description: Optional description

**Use Cases**:
- List view metadata without downloading files
- Verify evidence exists before downloading
- Display file information in UI
- Integration with case management systems

**Authorization**: Requires X-User-ID header (case ownership validated at gateway)
**Performance**: Fast metadata-only lookup (no file I/O)
    """,
    responses={
        200: {"description": "Evidence metadata returned successfully"},
        404: {"description": "Evidence not found"},
        500: {"description": "Database error"}
    }
)
async def get_evidence_metadata(
    evidence_id: str,
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
) -> EvidenceMetadataResponse:
    """Get evidence metadata"""
    evidence = await manager.get_evidence(evidence_id, db)

    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    return EvidenceMetadataResponse.from_evidence(evidence)


@router.get(
    "/{evidence_id}/download",
    summary="Download Evidence File",
    description="""
Download the actual file content for a specific evidence record.

**Workflow**:
1. Service looks up evidence metadata in database
2. Retrieves file from storage backend (local filesystem or S3)
3. Streams file content to client with appropriate Content-Type and Content-Disposition headers
4. Client receives file as download with original filename

**Response Format**:
- Content-Type: application/octet-stream
- Content-Disposition: attachment; filename={{original_filename}}
- Body: Binary file content (streamed)

**Storage Backend**:
Files are retrieved from the configured storage backend (local or S3) based on the storage_path in metadata.

**Use Cases**:
- Download evidence for local analysis
- Retrieve logs for debugging
- Export screenshots and documents
- Integrate with external analysis tools

**Performance**: Streamed response for efficient memory usage with large files

**Authorization**: Requires X-User-ID header (case ownership validated at gateway)
**File Size**: No size limits on download (limited only by upload MAX_FILE_SIZE)
    """,
    responses={
        200: {"description": "File download stream started successfully"},
        404: {"description": "Evidence not found or file missing from storage"},
        500: {"description": "Download failed due to storage error"}
    }
)
async def download_evidence(
    evidence_id: str,
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
):
    """Download evidence file"""
    try:
        file_content, filename = await manager.download_evidence(evidence_id, db)

        # Return as streaming response
        return StreamingResponse(
            BytesIO(file_content),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evidence not found")

    except Exception as e:
        logger.error(f"Evidence download failed: {e}")
        raise HTTPException(status_code=500, detail="Download failed")


@router.delete(
    "/{evidence_id}",
    status_code=204,
    summary="Delete Evidence",
    description="""
Permanently delete an evidence file and its metadata from the system.

**Workflow**:
1. Service looks up evidence record in database
2. Deletes file from storage backend (local filesystem or S3)
3. Removes metadata record from database
4. Returns 204 No Content on success

**Destructive Operation**:
⚠️ This operation is **permanent** and cannot be undone. The file is deleted from storage and metadata is removed from the database.

**Use Cases**:
- Remove incorrect or duplicate uploads
- Clean up test data
- Comply with data retention policies
- Free storage space

**Storage Cleanup**:
Both the database record and physical file are deleted. If file deletion fails, the operation may be partially completed (metadata removed but file remains).

**Authorization**: Requires X-User-ID header (case ownership validated at gateway)
**Logging**: Deletion is logged for audit purposes
    """,
    responses={
        204: {"description": "Evidence deleted successfully"},
        404: {"description": "Evidence not found"},
        500: {"description": "Deletion failed due to storage or database error"}
    }
)
async def delete_evidence(
    evidence_id: str,
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
):
    """Delete evidence"""
    deleted = await manager.delete_evidence(evidence_id, db)

    if not deleted:
        raise HTTPException(status_code=404, detail="Evidence not found")

    logger.info(f"User {x_user_id} deleted evidence: {evidence_id}")
    return None


@router.get(
    "",
    response_model=EvidenceListResponse,
    summary="List Evidence for Case",
    description="""
Retrieve a paginated list of evidence files associated with a specific case, with optional filtering by evidence type.

**Workflow**:
1. Client provides case_id (required) and optional filters
2. Service queries database for matching evidence records
3. Results are paginated based on page and page_size parameters
4. Returns list of evidence metadata with pagination info

**Query Parameters**:
- case_id: Case ID to filter by (required)
- page: Page number, 1-indexed (default: 1)
- page_size: Items per page, max 100 (default: 50)
- evidence_type: Filter by type (log/screenshot/document/metric/other)

**Response Structure**:
- evidence: Array of evidence metadata items
- total: Total number of matching evidence items
- page: Current page number
- page_size: Items per page
- total_pages: Total number of pages

**Use Cases**:
- Display evidence list for a case in UI
- Browse evidence files by type (e.g., all screenshots)
- Paginate through large evidence collections
- Verify evidence count for a case

**Performance**: Database query with indexes on case_id and evidence_type for fast filtering

**Authorization**: Requires X-User-ID header (case ownership validated at gateway)
    """,
    responses={
        200: {"description": "Evidence list returned successfully"},
        400: {"description": "Invalid query parameters"},
        500: {"description": "Database error"}
    }
)
async def list_evidence(
    case_id: str = Query(..., description="Case ID to list evidence for"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    evidence_type: Optional[EvidenceType] = Query(None, description="Filter by evidence type"),
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
) -> EvidenceListResponse:
    """List evidence for a case with pagination and filtering"""
    # Enforce page size limits
    page_size = min(page_size, settings.max_page_size)

    # Get evidence list
    evidence_list, total = await manager.list_case_evidence(
        case_id=case_id,
        db=db,
        page=page,
        page_size=page_size,
        evidence_type=evidence_type
    )

    # Convert to list items
    items = [
        EvidenceListItem(
            evidence_id=e.evidence_id,
            filename=e.filename,
            file_type=e.file_type,
            file_size=e.file_size,
            evidence_type=e.evidence_type,
            case_id=e.case_id,
            uploaded_at=e.uploaded_at
        )
        for e in evidence_list
    ]

    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return EvidenceListResponse(
        evidence=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get(
    "/case/{case_id}",
    response_model=EvidenceListResponse,
    summary="Get Case Evidence (Path Parameter)",
    description="""
Retrieve all evidence files for a specific case using case_id as a path parameter. Alternative endpoint to GET /api/v1/evidence with cleaner URL structure.

**Workflow**:
1. Client provides case_id in URL path
2. Service queries database for all evidence linked to the case
3. Results are paginated based on page and page_size parameters
4. Returns list of evidence metadata with pagination info

**URL Structure**:
- Path: /api/v1/evidence/case/{{case_id}}
- Query params: page, page_size

**Response Structure**:
- evidence: Array of evidence metadata items
- total: Total number of evidence items for the case
- page: Current page number
- page_size: Items per page
- total_pages: Total number of pages

**Difference from GET /api/v1/evidence**:
This endpoint uses case_id as a path parameter instead of query parameter, providing a more RESTful URL structure. Functionality is otherwise identical but does not support evidence_type filtering.

**Use Cases**:
- RESTful API design with resource-based URLs
- Get all evidence for a case without filtering
- Simpler URL structure for case-specific evidence retrieval

**Performance**: Database query with index on case_id for fast filtering

**Authorization**: Requires X-User-ID header (case ownership validated at gateway)
    """,
    responses={
        200: {"description": "Case evidence list returned successfully"},
        400: {"description": "Invalid pagination parameters"},
        500: {"description": "Database error"}
    }
)
async def get_case_evidence(
    case_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
) -> EvidenceListResponse:
    """Get all evidence for a specific case"""
    # Enforce page size limits
    page_size = min(page_size, settings.max_page_size)

    # Get evidence for case
    evidence_list, total = await manager.list_case_evidence(
        case_id=case_id,
        db=db,
        page=page,
        page_size=page_size
    )

    # Convert to list items
    items = [
        EvidenceListItem(
            evidence_id=e.evidence_id,
            filename=e.filename,
            file_type=e.file_type,
            file_size=e.file_size,
            evidence_type=e.evidence_type,
            case_id=e.case_id,
            uploaded_at=e.uploaded_at
        )
        for e in evidence_list
    ]

    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return EvidenceListResponse(
        evidence=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.post(
    "/{evidence_id}/link",
    status_code=200,
    summary="Link Evidence to Case",
    description="""
Associate an existing evidence file with a different case or update the case association.

**Workflow**:
1. Client provides evidence_id in URL and new case_id in request body
2. Service looks up evidence record in database
3. Updates case_id field to link evidence to new case
4. Returns success message with evidence_id and case_id

**Request Body**:
```json
{{
  "case_id": "case_xyz789"
}}
```

**Response Example**:
```json
{{
  "message": "Evidence linked to case",
  "evidence_id": "evidence_abc123",
  "case_id": "case_xyz789"
}}
```

**Use Cases**:
- Move evidence between cases when case structure changes
- Link orphaned evidence to appropriate cases
- Reorganize evidence after case merges or splits
- Correct case association mistakes

**Storage**: Only database metadata is updated; file storage location remains unchanged

**Authorization**: Requires X-User-ID header (case ownership validated at gateway for both cases)
**Logging**: Case linking is logged for audit purposes
    """,
    responses={
        200: {"description": "Evidence successfully linked to case"},
        404: {"description": "Evidence not found"},
        400: {"description": "Invalid case_id format"},
        500: {"description": "Database update failed"}
    }
)
async def link_evidence_to_case(
    evidence_id: str,
    request: LinkEvidenceToCaseRequest,
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
):
    """Link evidence to a case"""
    linked = await manager.link_to_case(
        evidence_id=evidence_id,
        case_id=request.case_id,
        db=db
    )

    if not linked:
        raise HTTPException(status_code=404, detail="Evidence not found")

    logger.info(f"Linked evidence {evidence_id} to case {request.case_id}")
    return {"message": "Evidence linked to case", "evidence_id": evidence_id, "case_id": request.case_id}


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Detailed Health Check",
    description="""
Comprehensive health check for Evidence Service including storage backend and database connectivity verification.

**Workflow**:
1. Checks storage backend availability (local filesystem or S3)
2. Executes test database query to verify connectivity
3. Determines overall health status (healthy/degraded)
4. Returns detailed health information

**Response Example**:
```json
{{
  "status": "healthy",
  "service": "fm-evidence-service",
  "storage_available": true,
  "database_available": true
}}
```

**Health Status Values**:
- healthy: All systems operational (storage and database accessible)
- degraded: One or more systems unavailable

**Storage Check**:
Verifies configured storage backend (local or S3) is accessible and can perform basic operations.

**Database Check**:
Executes simple SELECT query to verify database connectivity and responsiveness.

**Use Cases**:
- Deep health monitoring with component-level status
- Troubleshoot storage or database connectivity issues
- Monitor service dependencies
- Production readiness verification

**Performance**: Executes actual I/O operations (slower than /health endpoint)

**Authorization**: None required (public endpoint for monitoring)
    """,
    responses={
        200: {"description": "Health check completed (status may be healthy or degraded)"},
        500: {"description": "Health check failed to execute"}
    }
)
async def health_check(
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
) -> HealthResponse:
    """Health check endpoint"""
    # Check storage
    storage_ok = await manager.storage.health_check()

    # Check database (by executing simple query)
    db_ok = True
    try:
        await db.execute("SELECT 1")
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_ok = False

    # Overall status
    status = "healthy" if (storage_ok and db_ok) else "degraded"

    return HealthResponse(
        status=status,
        service="fm-evidence-service",
        storage_available=storage_ok,
        database_available=db_ok
    )
