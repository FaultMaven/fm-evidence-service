"""
Evidence Data Models

Core domain models for evidence file storage and metadata.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    """Evidence type classification"""
    LOG = "log"
    SCREENSHOT = "screenshot"
    METRIC = "metric"
    DOCUMENT = "document"
    OTHER = "other"


class Evidence(BaseModel):
    """Evidence file metadata and storage information"""

    evidence_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique evidence identifier"
    )
    user_id: str = Field(..., description="User who uploaded the evidence")
    case_id: Optional[str] = Field(None, description="Associated case ID")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    storage_path: str = Field(..., description="Storage location path")
    evidence_type: EvidenceType = Field(
        default=EvidenceType.OTHER,
        description="Evidence classification"
    )
    description: Optional[str] = Field(None, description="User-provided description")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    uploaded_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Upload timestamp"
    )
    uploaded_by: str = Field(..., description="User ID who uploaded")

    class Config:
        json_schema_extra = {
            "example": {
                "evidence_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user-123",
                "case_id": "case-456",
                "filename": "application.log",
                "file_type": "text/plain",
                "file_size": 102400,
                "storage_path": "uploads/user-123/case-456/550e8400-e29b-41d4-a716-446655440000_application.log",
                "evidence_type": "log",
                "description": "Application error logs from production",
                "metadata": {"environment": "production", "service": "api"},
                "uploaded_at": "2025-11-16T10:30:00Z",
                "uploaded_by": "user-123"
            }
        }
