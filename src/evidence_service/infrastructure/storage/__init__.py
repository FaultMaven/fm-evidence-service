"""Storage infrastructure module.

Provides deployment-neutral file storage via the StorageProvider interface.
"""

from evidence_service.infrastructure.storage.factory import get_storage_provider, reset_storage_provider
from evidence_service.infrastructure.storage.provider import StorageProvider
from evidence_service.infrastructure.storage.local_storage import LocalStorage
from evidence_service.infrastructure.storage.s3_storage import S3Storage

__all__ = [
    "get_storage_provider",
    "reset_storage_provider",
    "StorageProvider",
    "LocalStorage",
    "S3Storage",
]
