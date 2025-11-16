"""
Local Filesystem Storage

Local file storage implementation for development and testing.
"""

import logging
import os
from pathlib import Path
from typing import BinaryIO

import aiofiles

from evidence_service.config.settings import settings

logger = logging.getLogger(__name__)


class LocalStorage:
    """Local filesystem storage manager"""

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir or settings.local_upload_dir)
        self._ensure_base_dir()

    def _ensure_base_dir(self):
        """Ensure base directory exists"""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Local storage initialized at: {self.base_dir}")

    def _get_storage_path(self, user_id: str, case_id: str = None, filename: str = "") -> Path:
        """
        Get storage path for evidence file

        Path structure: {base_dir}/{user_id}/{case_id}/{filename}
        If case_id is None, uses 'unlinked' as placeholder
        """
        case_dir = case_id or "unlinked"
        path = self.base_dir / user_id / case_dir / filename
        return path

    async def save_file(
        self,
        file_content: bytes,
        user_id: str,
        evidence_id: str,
        filename: str,
        case_id: str = None
    ) -> str:
        """
        Save file to local storage

        Args:
            file_content: File bytes to save
            user_id: User ID
            evidence_id: Evidence UUID
            filename: Original filename
            case_id: Optional case ID

        Returns:
            Storage path (relative to base_dir)
        """
        # Create filename with evidence_id prefix
        storage_filename = f"{evidence_id}_{filename}"
        storage_path = self._get_storage_path(user_id, case_id, storage_filename)

        # Ensure directory exists
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file asynchronously
        async with aiofiles.open(storage_path, "wb") as f:
            await f.write(file_content)

        # Return relative path
        relative_path = str(storage_path.relative_to(self.base_dir))
        logger.info(f"Saved file to: {relative_path}")
        return relative_path

    async def get_file(self, storage_path: str) -> bytes:
        """
        Retrieve file from local storage

        Args:
            storage_path: Relative storage path

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        full_path = self.base_dir / storage_path

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {storage_path}")

        async with aiofiles.open(full_path, "rb") as f:
            content = await f.read()

        logger.info(f"Retrieved file from: {storage_path}")
        return content

    async def delete_file(self, storage_path: str) -> bool:
        """
        Delete file from local storage

        Args:
            storage_path: Relative storage path

        Returns:
            True if deleted, False if not found
        """
        full_path = self.base_dir / storage_path

        if not full_path.exists():
            logger.warning(f"File not found for deletion: {storage_path}")
            return False

        # Delete file
        full_path.unlink()
        logger.info(f"Deleted file: {storage_path}")

        # Clean up empty directories
        try:
            full_path.parent.rmdir()
            full_path.parent.parent.rmdir()
        except OSError:
            # Directory not empty, that's fine
            pass

        return True

    async def file_exists(self, storage_path: str) -> bool:
        """Check if file exists in storage"""
        full_path = self.base_dir / storage_path
        return full_path.exists()

    async def health_check(self) -> bool:
        """Check storage health"""
        try:
            # Verify base directory is writable
            test_file = self.base_dir / ".health_check"
            test_file.touch()
            test_file.unlink()
            return True
        except Exception as e:
            logger.error(f"Storage health check failed: {e}")
            return False
