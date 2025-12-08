"""Local Filesystem Storage Implementation

Async local file storage for development and self-hosted deployments.
Uses aiofiles for non-blocking I/O to match S3Storage performance characteristics.
"""

import logging
import os
from pathlib import Path
from typing import AsyncGenerator, BinaryIO

import aiofiles
from fastapi import HTTPException

from evidence_service.infrastructure.storage.provider import StorageProvider

logger = logging.getLogger(__name__)


class LocalStorage(StorageProvider):
    """Local filesystem storage provider for development and self-hosted deployments.

    Uses aiofiles for async operations to avoid blocking the FastAPI event loop.
    Maintains performance parity with S3Storage for deployment neutrality.
    """

    def __init__(self, base_path: str = None):
        """Initialize local storage provider.

        Args:
            base_path: Base directory for file storage (default: ./data/uploads)

        Raises:
            ValueError: If base_path is not provided
        """
        if not base_path:
            base_path = os.getenv("STORAGE_LOCAL_PATH", "./data/uploads")

        self.base_path = Path(base_path).resolve()

        # Ensure directory exists on startup
        self.base_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Local storage initialized at: {self.base_path}")

    def _get_path(self, key: str) -> Path:
        """Get full filesystem path from storage key.

        Args:
            key: Storage key (relative path)

        Returns:
            Resolved absolute path

        Raises:
            HTTPException: If path attempts directory traversal
        """
        # Security: Prevent directory traversal attacks (e.g., "../../etc/passwd")
        safe_path = (self.base_path / key).resolve()

        if not safe_path.is_relative_to(self.base_path):
            logger.error(f"Path traversal attempt detected: {key}")
            raise HTTPException(status_code=400, detail="Invalid file path")

        return safe_path

    async def upload(
        self,
        file_stream: BinaryIO,
        key: str,
        content_type: str,
        user_id: str,
        case_id: str = None
    ) -> str:
        """Upload file to local filesystem.

        Args:
            file_stream: Binary file stream
            key: Storage key (relative path)
            content_type: MIME type (for logging/auditing)
            user_id: User ID (for logging/auditing)
            case_id: Optional case ID (for logging/auditing)

        Returns:
            Storage key (same as input for local storage)

        Raises:
            HTTPException: If upload fails
        """
        file_path = self._get_path(key)

        # Ensure subdirectories exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Reset stream pointer
            file_stream.seek(0)

            # Write file asynchronously in 64KB chunks
            async with aiofiles.open(file_path, 'wb') as out_file:
                while content := file_stream.read(65536):  # 64KB chunks
                    await out_file.write(content)

            logger.info(f"Uploaded file to local storage: {file_path}")
            return key

        except Exception as e:
            logger.error(f"Local upload failed for {key}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Local upload failed: {str(e)}"
            )

    async def download_stream(self, key: str) -> AsyncGenerator[bytes, None]:
        """Stream file from local filesystem.

        Args:
            key: Storage key (relative path)

        Yields:
            Chunks of file bytes

        Raises:
            HTTPException: If file not found or read fails
        """
        file_path = self._get_path(key)

        if not file_path.exists():
            logger.warning(f"File not found in local storage: {key}")
            raise HTTPException(status_code=404, detail=f"File not found: {key}")

        try:
            async with aiofiles.open(file_path, 'rb') as in_file:
                while chunk := await in_file.read(65536):  # 64KB chunks
                    yield chunk

            logger.info(f"Streamed file from local storage: {file_path}")

        except Exception as e:
            logger.error(f"Local download failed for {key}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Local download failed: {str(e)}"
            )

    async def delete(self, key: str) -> bool:
        """Delete file from local filesystem.

        Args:
            key: Storage key (relative path)

        Returns:
            True if deleted successfully, False if file not found

        Note:
            Attempts to clean up empty parent directories
        """
        file_path = self._get_path(key)

        if not file_path.exists():
            logger.warning(f"File not found for deletion: {key}")
            return False

        try:
            # Delete file
            os.remove(file_path)
            logger.info(f"Deleted file from local storage: {file_path}")

            # Clean up empty directories (best effort)
            try:
                file_path.parent.rmdir()
                file_path.parent.parent.rmdir()
            except OSError:
                # Directory not empty, that's fine
                pass

            return True

        except OSError as e:
            logger.error(f"Failed to delete file {key}: {e}")
            return False

    async def generate_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """Generate URL for file access.

        For local storage, we return an API route that proxies the file.
        True presigned URLs require a separate media serving endpoint.

        Args:
            key: Storage key (relative path)
            expiration: URL expiration in seconds (not enforced for local)

        Returns:
            API route to download file

        Note:
            This assumes the API has a /evidence/{evidence_id}/download endpoint.
            For production local deployments, consider using nginx for direct file serving.
        """
        # Extract evidence_id from key (format: user_id/case_id/evidence_id_filename)
        # This is a simplified implementation - adjust based on your routing
        evidence_id = key.split('/')[-1].split('_')[0]

        # Return API route (API Gateway will proxy this to the evidence service)
        url = f"/api/v1/evidence/{evidence_id}/download"

        logger.debug(f"Generated local URL for {key}: {url}")
        return url

    async def file_exists(self, key: str) -> bool:
        """Check if file exists in local storage.

        Args:
            key: Storage key (relative path)

        Returns:
            True if file exists, False otherwise
        """
        try:
            file_path = self._get_path(key)
            return file_path.exists()
        except HTTPException:
            # Path traversal attempt
            return False

    async def health_check(self) -> bool:
        """Check local storage health by verifying write access.

        Returns:
            True if storage is writable, False otherwise
        """
        try:
            # Verify base directory is writable
            test_file = self.base_path / ".health_check"
            test_file.touch()
            test_file.unlink()

            logger.debug(f"Local storage health check passed: {self.base_path}")
            return True

        except Exception as e:
            logger.error(f"Local storage health check failed: {e}")
            return False
