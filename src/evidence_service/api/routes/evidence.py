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


@router.post("", response_model=EvidenceUploadResponse, status_code=201)
async def upload_evidence(
    file: UploadFile = File(..., description="Evidence file to upload"),
    case_id: Optional[str] = Form(None, description="Case ID to link evidence to"),
    description: Optional[str] = Form(None, description="Evidence description"),
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
) -> EvidenceUploadResponse:
    """
    Upload evidence file

    Multipart form data with file upload.
    Trust X-User-ID header from API gateway (no JWT validation needed).

    Args:
        file: Evidence file (multipart upload)
        case_id: Optional case ID to link
        description: Optional description
        x_user_id: User ID from API gateway header
        db: Database session
        manager: Evidence manager

    Returns:
        Evidence upload response with metadata

    Raises:
        400: File validation failed
        413: File too large
        500: Upload failed
    """
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


@router.get("/{evidence_id}", response_model=EvidenceMetadataResponse)
async def get_evidence_metadata(
    evidence_id: str,
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
) -> EvidenceMetadataResponse:
    """
    Get evidence metadata

    Args:
        evidence_id: Evidence ID
        x_user_id: User ID from API gateway header (for future authorization)
        db: Database session
        manager: Evidence manager

    Returns:
        Evidence metadata

    Raises:
        404: Evidence not found

    Note:
        Authorization through case ownership should be handled at API gateway
    """
    evidence = await manager.get_evidence(evidence_id, db)

    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    return EvidenceMetadataResponse.from_evidence(evidence)


@router.get("/{evidence_id}/download")
async def download_evidence(
    evidence_id: str,
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
):
    """
    Download evidence file

    Args:
        evidence_id: Evidence ID
        x_user_id: User ID from API gateway header (for future authorization)
        db: Database session
        manager: Evidence manager

    Returns:
        File download stream

    Raises:
        404: Evidence not found

    Note:
        Authorization through case ownership should be handled at API gateway
    """
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


@router.delete("/{evidence_id}", status_code=204)
async def delete_evidence(
    evidence_id: str,
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
):
    """
    Delete evidence

    Args:
        evidence_id: Evidence ID
        x_user_id: User ID from API gateway header (for logging)
        db: Database session
        manager: Evidence manager

    Returns:
        204 No Content

    Raises:
        404: Evidence not found

    Note:
        Authorization through case ownership should be handled at API gateway
    """
    deleted = await manager.delete_evidence(evidence_id, db)

    if not deleted:
        raise HTTPException(status_code=404, detail="Evidence not found")

    logger.info(f"User {x_user_id} deleted evidence: {evidence_id}")
    return None


@router.get("", response_model=EvidenceListResponse)
async def list_evidence(
    case_id: str = Query(..., description="Case ID to list evidence for"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    evidence_type: Optional[EvidenceType] = Query(None, description="Filter by evidence type"),
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
) -> EvidenceListResponse:
    """
    List evidence for a case with pagination and filtering

    Args:
        case_id: Case ID to list evidence for (required)
        page: Page number (1-indexed)
        page_size: Items per page (max 100)
        evidence_type: Optional evidence type filter
        x_user_id: User ID from API gateway header (for future authorization)
        db: Database session
        manager: Evidence manager

    Returns:
        Paginated list of evidence

    Note:
        Authorization through case ownership should be handled at API gateway
    """
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


@router.get("/case/{case_id}", response_model=EvidenceListResponse)
async def get_case_evidence(
    case_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
) -> EvidenceListResponse:
    """
    Get all evidence for a specific case

    Args:
        case_id: Case ID
        page: Page number
        page_size: Items per page
        x_user_id: User ID from API gateway header (for future authorization)
        db: Database session
        manager: Evidence manager

    Returns:
        Paginated list of case evidence

    Note:
        Authorization through case ownership should be handled at API gateway
    """
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


@router.post("/{evidence_id}/link", status_code=200)
async def link_evidence_to_case(
    evidence_id: str,
    request: LinkEvidenceToCaseRequest,
    x_user_id: str = Header(..., alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
):
    """
    Link evidence to a case

    Args:
        evidence_id: Evidence ID
        request: Link request with case_id
        x_user_id: User ID from API gateway header (for logging)
        db: Database session
        manager: Evidence manager

    Returns:
        Success message

    Raises:
        404: Evidence not found

    Note:
        Authorization through case ownership should be handled at API gateway
    """
    linked = await manager.link_to_case(
        evidence_id=evidence_id,
        case_id=request.case_id,
        db=db
    )

    if not linked:
        raise HTTPException(status_code=404, detail="Evidence not found")

    logger.info(f"Linked evidence {evidence_id} to case {request.case_id}")
    return {"message": "Evidence linked to case", "evidence_id": evidence_id, "case_id": request.case_id}


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check(
    db: AsyncSession = Depends(get_db),
    manager: EvidenceManager = Depends(get_evidence_manager)
) -> HealthResponse:
    """
    Health check endpoint

    Returns:
        Health status including storage and database availability
    """
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
