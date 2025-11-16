"""
Evidence Manager

Core business logic for evidence file management and operations.
"""

import logging
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from evidence_service.config.settings import settings
from evidence_service.models.evidence import Evidence, EvidenceType
from evidence_service.infrastructure.database.models import EvidenceDB
from evidence_service.infrastructure.storage.local_storage import LocalStorage
from evidence_service.infrastructure.storage.s3_storage import S3Storage

logger = logging.getLogger(__name__)


class EvidenceManager:
    """Business logic for evidence management"""

    def __init__(self):
        # Initialize storage based on configuration
        if settings.storage_type == "s3":
            self.storage = S3Storage()
        else:
            self.storage = LocalStorage()

    def _classify_evidence_type(self, filename: str, file_type: str) -> EvidenceType:
        """
        Classify evidence type based on filename and MIME type

        Args:
            filename: Original filename
            file_type: MIME type

        Returns:
            EvidenceType classification
        """
        extension = Path(filename).suffix.lower()

        # Log files
        if extension in [".log", ".txt"] or "text" in file_type:
            return EvidenceType.LOG

        # Screenshots/images
        if extension in [".png", ".jpg", ".jpeg", ".gif"] or "image" in file_type:
            return EvidenceType.SCREENSHOT

        # Documents
        if extension in [".pdf", ".doc", ".docx"] or "pdf" in file_type:
            return EvidenceType.DOCUMENT

        # Metrics/JSON
        if extension == ".json" or "json" in file_type:
            return EvidenceType.METRIC

        return EvidenceType.OTHER

    def _validate_file(self, filename: str, file_size: int) -> None:
        """
        Validate file before upload

        Args:
            filename: Original filename
            file_size: File size in bytes

        Raises:
            ValueError: If validation fails
        """
        # Check file size
        if file_size > settings.max_file_size_bytes:
            raise ValueError(
                f"File too large: {file_size} bytes (max: {settings.max_file_size_mb}MB)"
            )

        # Check file extension
        extension = Path(filename).suffix.lower()
        if extension not in settings.allowed_extensions:
            raise ValueError(
                f"File type not allowed: {extension} (allowed: {settings.allowed_file_types})"
            )

    async def upload_evidence(
        self,
        file_content: bytes,
        filename: str,
        user_id: str,
        case_id: Optional[str] = None,
        description: Optional[str] = None,
        db: AsyncSession = None
    ) -> Evidence:
        """
        Upload evidence file

        Args:
            file_content: File bytes
            filename: Original filename
            user_id: User ID from X-User-ID header
            case_id: Optional case ID to link
            description: Optional description
            db: Database session

        Returns:
            Evidence metadata

        Raises:
            ValueError: If validation fails
        """
        # Validate file
        file_size = len(file_content)
        self._validate_file(filename, file_size)

        # Generate evidence ID
        evidence_id = str(uuid4())

        # Determine MIME type
        file_type, _ = mimetypes.guess_type(filename)
        file_type = file_type or "application/octet-stream"

        # Classify evidence type
        evidence_type = self._classify_evidence_type(filename, file_type)

        # Save file to storage
        storage_path = await self.storage.save_file(
            file_content=file_content,
            user_id=user_id,
            evidence_id=evidence_id,
            filename=filename,
            case_id=case_id
        )

        # Create Evidence model
        evidence = Evidence(
            evidence_id=evidence_id,
            user_id=user_id,
            case_id=case_id,
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            storage_path=storage_path,
            evidence_type=evidence_type,
            description=description,
            uploaded_at=datetime.utcnow(),
            uploaded_by=user_id
        )

        # Save metadata to database
        if db:
            evidence_db = EvidenceDB(
                evidence_id=evidence.evidence_id,
                user_id=evidence.user_id,
                case_id=evidence.case_id,
                filename=evidence.filename,
                file_type=evidence.file_type,
                file_size=evidence.file_size,
                storage_path=evidence.storage_path,
                evidence_type=evidence.evidence_type.value,
                description=evidence.description,
                evidence_metadata=evidence.metadata,
                uploaded_at=evidence.uploaded_at,
                uploaded_by=evidence.uploaded_by
            )
            db.add(evidence_db)
            await db.commit()

        logger.info(f"Uploaded evidence: {evidence_id} ({filename})")
        return evidence

    async def get_evidence(self, evidence_id: str, user_id: str, db: AsyncSession) -> Optional[Evidence]:
        """
        Get evidence metadata

        Args:
            evidence_id: Evidence ID
            user_id: User ID (for authorization)
            db: Database session

        Returns:
            Evidence metadata or None
        """
        stmt = select(EvidenceDB).where(
            and_(
                EvidenceDB.evidence_id == evidence_id,
                EvidenceDB.user_id == user_id
            )
        )
        result = await db.execute(stmt)
        evidence_db = result.scalar_one_or_none()

        if not evidence_db:
            return None

        return Evidence(
            evidence_id=evidence_db.evidence_id,
            user_id=evidence_db.user_id,
            case_id=evidence_db.case_id,
            filename=evidence_db.filename,
            file_type=evidence_db.file_type,
            file_size=evidence_db.file_size,
            storage_path=evidence_db.storage_path,
            evidence_type=EvidenceType(evidence_db.evidence_type),
            description=evidence_db.description,
            metadata=evidence_db.evidence_metadata or {},
            uploaded_at=evidence_db.uploaded_at,
            uploaded_by=evidence_db.uploaded_by
        )

    async def download_evidence(self, evidence_id: str, user_id: str, db: AsyncSession) -> tuple[bytes, str]:
        """
        Download evidence file

        Args:
            evidence_id: Evidence ID
            user_id: User ID (for authorization)
            db: Database session

        Returns:
            Tuple of (file_content, filename)

        Raises:
            FileNotFoundError: If evidence not found
        """
        # Get metadata
        evidence = await self.get_evidence(evidence_id, user_id, db)
        if not evidence:
            raise FileNotFoundError(f"Evidence not found: {evidence_id}")

        # Download from storage
        file_content = await self.storage.get_file(evidence.storage_path)

        return file_content, evidence.filename

    async def delete_evidence(self, evidence_id: str, user_id: str, db: AsyncSession) -> bool:
        """
        Delete evidence

        Args:
            evidence_id: Evidence ID
            user_id: User ID (for authorization)
            db: Database session

        Returns:
            True if deleted, False if not found
        """
        # Get metadata first
        evidence = await self.get_evidence(evidence_id, user_id, db)
        if not evidence:
            return False

        # Delete from storage
        await self.storage.delete_file(evidence.storage_path)

        # Delete from database
        stmt = select(EvidenceDB).where(EvidenceDB.evidence_id == evidence_id)
        result = await db.execute(stmt)
        evidence_db = result.scalar_one_or_none()

        if evidence_db:
            await db.delete(evidence_db)
            await db.commit()

        logger.info(f"Deleted evidence: {evidence_id}")
        return True

    async def list_user_evidence(
        self,
        user_id: str,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 50,
        case_id: Optional[str] = None,
        evidence_type: Optional[EvidenceType] = None
    ) -> tuple[List[Evidence], int]:
        """
        List user's evidence with pagination and filtering

        Args:
            user_id: User ID
            db: Database session
            page: Page number (1-indexed)
            page_size: Items per page
            case_id: Optional case ID filter
            evidence_type: Optional evidence type filter

        Returns:
            Tuple of (evidence_list, total_count)
        """
        # Build query
        conditions = [EvidenceDB.user_id == user_id]

        if case_id:
            conditions.append(EvidenceDB.case_id == case_id)

        if evidence_type:
            conditions.append(EvidenceDB.evidence_type == evidence_type.value)

        # Get total count
        count_stmt = select(EvidenceDB).where(and_(*conditions))
        count_result = await db.execute(count_stmt)
        total_count = len(count_result.scalars().all())

        # Get paginated results
        offset = (page - 1) * page_size
        stmt = (
            select(EvidenceDB)
            .where(and_(*conditions))
            .order_by(EvidenceDB.uploaded_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        evidence_list_db = result.scalars().all()

        # Convert to Evidence models
        evidence_list = [
            Evidence(
                evidence_id=e.evidence_id,
                user_id=e.user_id,
                case_id=e.case_id,
                filename=e.filename,
                file_type=e.file_type,
                file_size=e.file_size,
                storage_path=e.storage_path,
                evidence_type=EvidenceType(e.evidence_type),
                description=e.description,
                metadata=e.evidence_metadata or {},
                uploaded_at=e.uploaded_at,
                uploaded_by=e.uploaded_by
            )
            for e in evidence_list_db
        ]

        return evidence_list, total_count

    async def link_to_case(self, evidence_id: str, case_id: str, user_id: str, db: AsyncSession) -> bool:
        """
        Link evidence to a case

        Args:
            evidence_id: Evidence ID
            case_id: Case ID
            user_id: User ID (for authorization)
            db: Database session

        Returns:
            True if linked, False if not found
        """
        stmt = select(EvidenceDB).where(
            and_(
                EvidenceDB.evidence_id == evidence_id,
                EvidenceDB.user_id == user_id
            )
        )
        result = await db.execute(stmt)
        evidence_db = result.scalar_one_or_none()

        if not evidence_db:
            return False

        evidence_db.case_id = case_id
        await db.commit()

        logger.info(f"Linked evidence {evidence_id} to case {case_id}")
        return True
