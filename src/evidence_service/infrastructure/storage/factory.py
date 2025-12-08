"""Storage Provider Factory

Factory pattern for deployment-neutral storage selection.
Chooses between local filesystem and S3 based on STORAGE_PROVIDER env var.
"""

import logging
import os
from typing import Optional

from evidence_service.infrastructure.storage.provider import StorageProvider
from evidence_service.infrastructure.storage.local_storage import LocalStorage
from evidence_service.infrastructure.storage.s3_storage import S3Storage

logger = logging.getLogger(__name__)

# Singleton instance to avoid recreating sessions
_storage_instance: Optional[StorageProvider] = None


def get_storage_provider() -> StorageProvider:
    """Get or create the global storage provider instance.

    Uses STORAGE_PROVIDER environment variable to determine provider type:
    - "local" (default): Local filesystem storage
    - "s3": AWS S3 or MinIO storage

    Returns:
        StorageProvider instance (LocalStorage or S3Storage)

    Environment Variables:
        STORAGE_PROVIDER: "local" or "s3" (default: "local")

        For local storage:
            STORAGE_LOCAL_PATH: Base directory (default: "./data/uploads")

        For S3 storage:
            S3_BUCKET_NAME: S3 bucket name (required)
            S3_REGION: AWS region (default: "us-east-1")
            S3_ENDPOINT_URL: Custom endpoint for MinIO/LocalStack (optional)
            AWS_ACCESS_KEY_ID: AWS access key (optional, uses boto3 defaults)
            AWS_SECRET_ACCESS_KEY: AWS secret key (optional, uses boto3 defaults)

    Example:
        ```python
        # Self-hosted deployment (docker-compose)
        STORAGE_PROVIDER=local
        STORAGE_LOCAL_PATH=/data/uploads

        # Enterprise K8s with AWS S3
        STORAGE_PROVIDER=s3
        S3_BUCKET_NAME=faultmaven-evidence-prod
        S3_REGION=us-west-2

        # Enterprise K8s with MinIO
        STORAGE_PROVIDER=s3
        S3_BUCKET_NAME=evidence
        S3_ENDPOINT_URL=http://minio:9000
        AWS_ACCESS_KEY_ID=minioadmin
        AWS_SECRET_ACCESS_KEY=minioadmin
        ```
    """
    global _storage_instance

    if _storage_instance is not None:
        return _storage_instance

    provider_type = os.getenv("STORAGE_PROVIDER", "local").lower()

    logger.info(f"Initializing storage provider: {provider_type}")

    if provider_type == "s3":
        # S3 or MinIO storage for production K8s
        bucket_name = os.getenv("S3_BUCKET_NAME")
        region = os.getenv("S3_REGION", "us-east-1")
        endpoint_url = os.getenv("S3_ENDPOINT_URL")
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

        _storage_instance = S3Storage(
            bucket_name=bucket_name,
            region=region,
            endpoint_url=endpoint_url,
            access_key=access_key,
            secret_key=secret_key
        )

        logger.info(
            f"S3 storage provider initialized: "
            f"bucket={bucket_name}, "
            f"endpoint={endpoint_url or 'AWS'}"
        )

    else:
        # Local filesystem storage for development and self-hosted
        local_path = os.getenv("STORAGE_LOCAL_PATH", "./data/uploads")

        _storage_instance = LocalStorage(base_path=local_path)

        logger.info(f"Local storage provider initialized: path={local_path}")

    return _storage_instance


def reset_storage_provider():
    """Reset the global storage provider instance.

    Used for testing or reconfiguration. Should not be called in production code.
    """
    global _storage_instance
    _storage_instance = None
    logger.warning("Storage provider instance reset")
