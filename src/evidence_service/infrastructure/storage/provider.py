"""Storage Provider Interface

Abstract base class defining the contract for file storage implementations.
Supports both local filesystem (development/self-hosted) and S3 (enterprise/K8s).
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, BinaryIO


class StorageProvider(ABC):
    """Abstract storage provider interface for deployment-neutral file storage."""

    @abstractmethod
    async def upload(
        self,
        file_stream: BinaryIO,
        key: str,
        content_type: str,
        user_id: str,
        case_id: str = None
    ) -> str:
        """Upload a file and return a retrievable path/URL.

        Args:
            file_stream: Binary file stream (SpooledTemporaryFile or similar)
            key: Unique filename/path (e.g., "evidence_id_filename.pdf")
            content_type: MIME type (e.g., "application/pdf")
            user_id: User ID for organizing files
            case_id: Optional case ID for organizing files

        Returns:
            Storage path or key that can be used to retrieve the file

        Raises:
            Exception: If upload fails
        """
        pass

    @abstractmethod
    async def download_stream(self, key: str) -> AsyncGenerator[bytes, None]:
        """Stream file content as bytes.

        Args:
            key: Storage path/key returned from upload()

        Yields:
            Chunks of file bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a file from storage.

        Args:
            key: Storage path/key to delete

        Returns:
            True if deleted successfully, False if file not found
        """
        pass

    @abstractmethod
    async def generate_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """Generate a temporary public/private URL for direct file access.

        This is used when the frontend needs to view/download files directly
        without proxying through the service.

        Args:
            key: Storage path/key
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL string

        Raises:
            Exception: If URL generation fails
        """
        pass

    @abstractmethod
    async def file_exists(self, key: str) -> bool:
        """Check if a file exists in storage.

        Args:
            key: Storage path/key to check

        Returns:
            True if file exists, False otherwise
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if storage backend is healthy and accessible.

        Returns:
            True if storage is healthy, False otherwise
        """
        pass
