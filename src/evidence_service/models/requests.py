"""
API Request and Response Models

Pydantic models for API input/output validation.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field

from .evidence import Evidence, EvidenceType


class EvidenceUploadResponse(BaseModel):
    """Response after successful file upload"""

    evidence_id: str = Field(..., description="Unique evidence identifier")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., description="File size in bytes")
    evidence_type: EvidenceType = Field(..., description="Evidence classification")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    message: str = Field(default="Evidence uploaded successfully")


class EvidenceMetadataResponse(BaseModel):
    """Evidence metadata response"""

    evidence_id: str
    user_id: str
    case_id: Optional[str]
    filename: str
    file_type: str
    file_size: int
    evidence_type: EvidenceType
    description: Optional[str]
    metadata: Dict[str, Any]
    uploaded_at: datetime
    uploaded_by: str

    @classmethod
    def from_evidence(cls, evidence: Evidence) -> "EvidenceMetadataResponse":
        """Create response from Evidence model"""
        return cls(
            evidence_id=evidence.evidence_id,
            user_id=evidence.user_id,
            case_id=evidence.case_id,
            filename=evidence.filename,
            file_type=evidence.file_type,
            file_size=evidence.file_size,
            evidence_type=evidence.evidence_type,
            description=evidence.description,
            metadata=evidence.metadata,
            uploaded_at=evidence.uploaded_at,
            uploaded_by=evidence.uploaded_by
        )


class EvidenceListItem(BaseModel):
    """Simplified evidence item for list responses"""

    evidence_id: str
    filename: str
    file_type: str
    file_size: int
    evidence_type: EvidenceType
    case_id: Optional[str]
    uploaded_at: datetime


class EvidenceListResponse(BaseModel):
    """Paginated list of evidence"""

    evidence: List[EvidenceListItem] = Field(default_factory=list)
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_pages: int = Field(..., ge=0)


class LinkEvidenceToCaseRequest(BaseModel):
    """Request to link evidence to a case"""

    case_id: str = Field(..., description="Case ID to link evidence to")
    description: Optional[str] = Field(None, description="Optional description")


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = Field(default="healthy")
    service: str = Field(default="fm-evidence-service")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    storage_available: bool = Field(default=True)
    database_available: bool = Field(default=True)
