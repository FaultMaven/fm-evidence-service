"""S3/MinIO Storage Implementation

Production-ready S3-compatible storage using aioboto3 for non-blocking async I/O.
Supports AWS S3 and self-hosted MinIO for enterprise deployments.
"""

import logging
import os
from typing import AsyncGenerator, BinaryIO

import aioboto3
from botocore.exceptions import ClientError
from fastapi import HTTPException

from evidence_service.infrastructure.storage.provider import StorageProvider

logger = logging.getLogger(__name__)


class S3Storage(StorageProvider):
    """S3/MinIO storage provider for production Kubernetes deployments.

    Uses aioboto3 for async operations to avoid blocking the FastAPI event loop.
    Supports both AWS S3 and self-hosted MinIO via endpoint_url configuration.
    """

    def __init__(
        self,
        bucket_name: str = None,
        region: str = None,
        endpoint_url: str = None,
        access_key: str = None,
        secret_key: str = None
    ):
        """Initialize S3 storage provider.

        Args:
            bucket_name: S3 bucket name (required)
            region: AWS region (default: us-east-1)
            endpoint_url: Custom S3 endpoint for MinIO/LocalStack (optional)
            access_key: AWS access key ID (optional, falls back to env)
            secret_key: AWS secret access key (optional, falls back to env)

        Raises:
            ValueError: If bucket_name is not provided
        """
        self.bucket_name = bucket_name or os.getenv("S3_BUCKET_NAME")
        self.region = region or os.getenv("S3_REGION", "us-east-1")
        self.endpoint_url = endpoint_url or os.getenv("S3_ENDPOINT_URL")
        self.access_key = access_key or os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")

        if not self.bucket_name:
            raise ValueError(
                "S3_BUCKET_NAME environment variable or bucket_name parameter is required"
            )

        # Create aioboto3 session
        self.session = aioboto3.Session(
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region
        )

        logger.info(
            f"S3 storage initialized - bucket: {self.bucket_name}, "
            f"region: {self.region}, "
            f"endpoint: {self.endpoint_url or 'AWS'}"
        )

    def _build_key(self, user_id: str, evidence_id: str, filename: str, case_id: str = None) -> str:
        """Build S3 object key with hierarchical structure.

        Structure: {user_id}/{case_id or 'unlinked'}/{evidence_id}_{filename}

        Args:
            user_id: User ID
            evidence_id: Evidence UUID
            filename: Original filename
            case_id: Optional case ID

        Returns:
            S3 object key string
        """
        case_dir = case_id or "unlinked"
        return f"{user_id}/{case_dir}/{evidence_id}_{filename}"

    async def upload(
        self,
        file_stream: BinaryIO,
        key: str,
        content_type: str,
        user_id: str,
        case_id: str = None
    ) -> str:
        """Upload file to S3 bucket.

        Args:
            file_stream: Binary file stream
            key: Full S3 key (already constructed by caller)
            content_type: MIME type
            user_id: User ID (for logging/auditing)
            case_id: Optional case ID (for logging/auditing)

        Returns:
            S3 object key

        Raises:
            HTTPException: If upload fails
        """
        try:
            async with self.session.client(
                "s3",
                region_name=self.region,
                endpoint_url=self.endpoint_url
            ) as s3:
                # Reset stream pointer
                file_stream.seek(0)

                # Upload file
                await s3.upload_fileobj(
                    file_stream,
                    self.bucket_name,
                    key,
                    ExtraArgs={"ContentType": content_type}
                )

                logger.info(f"Uploaded file to S3: s3://{self.bucket_name}/{key}")
                return key

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"S3 upload failed (error: {error_code}): {e}")
            raise HTTPException(
                status_code=500,
                detail=f"S3 upload failed: {error_code}"
            )
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"S3 upload failed: {str(e)}"
            )

    async def download_stream(self, key: str) -> AsyncGenerator[bytes, None]:
        """Stream file from S3.

        Args:
            key: S3 object key

        Yields:
            Chunks of file bytes

        Raises:
            HTTPException: If file not found or download fails
        """
        async with self.session.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint_url
        ) as s3:
            try:
                response = await s3.get_object(Bucket=self.bucket_name, Key=key)

                # Stream the response body
                async for chunk in response['Body'].iter_chunks(chunk_size=65536):  # 64KB chunks
                    yield chunk

                logger.info(f"Streamed file from S3: s3://{self.bucket_name}/{key}")

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "NoSuchKey":
                    logger.warning(f"File not found in S3: {key}")
                    raise HTTPException(status_code=404, detail=f"File not found: {key}")
                else:
                    logger.error(f"S3 download failed (error: {error_code}): {e}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"S3 download failed: {error_code}"
                    )
            except Exception as e:
                logger.error(f"S3 download failed: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"S3 download failed: {str(e)}"
                )

    async def delete(self, key: str) -> bool:
        """Delete file from S3.

        Args:
            key: S3 object key

        Returns:
            True if deleted successfully

        Note:
            S3 delete_object succeeds even if object doesn't exist
        """
        try:
            async with self.session.client(
                "s3",
                region_name=self.region,
                endpoint_url=self.endpoint_url
            ) as s3:
                await s3.delete_object(Bucket=self.bucket_name, Key=key)
                logger.info(f"Deleted file from S3: s3://{self.bucket_name}/{key}")
                return True

        except Exception as e:
            logger.error(f"S3 delete failed for {key}: {e}")
            return False

    async def generate_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """Generate presigned URL for direct file access.

        Args:
            key: S3 object key
            expiration: URL expiration in seconds (default: 1 hour)

        Returns:
            Presigned URL string

        Raises:
            HTTPException: If URL generation fails
        """
        try:
            async with self.session.client(
                "s3",
                region_name=self.region,
                endpoint_url=self.endpoint_url
            ) as s3:
                url = await s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': key},
                    ExpiresIn=expiration
                )

                logger.debug(f"Generated presigned URL for {key} (expires in {expiration}s)")
                return url

        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {key}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Could not generate signed URL: {str(e)}"
            )

    async def file_exists(self, key: str) -> bool:
        """Check if file exists in S3.

        Args:
            key: S3 object key

        Returns:
            True if file exists, False otherwise
        """
        try:
            async with self.session.client(
                "s3",
                region_name=self.region,
                endpoint_url=self.endpoint_url
            ) as s3:
                await s3.head_object(Bucket=self.bucket_name, Key=key)
                return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404":
                return False
            else:
                logger.error(f"Error checking file existence for {key}: {e}")
                return False
        except Exception as e:
            logger.error(f"Error checking file existence for {key}: {e}")
            return False

    async def health_check(self) -> bool:
        """Check S3 storage health by verifying bucket access.

        Returns:
            True if S3 is accessible and bucket exists, False otherwise
        """
        try:
            async with self.session.client(
                "s3",
                region_name=self.region,
                endpoint_url=self.endpoint_url
            ) as s3:
                # Try to list objects (limit 1) to verify access
                await s3.list_objects_v2(Bucket=self.bucket_name, MaxKeys=1)
                logger.debug(f"S3 health check passed for bucket: {self.bucket_name}")
                return True

        except Exception as e:
            logger.error(f"S3 health check failed: {e}")
            return False
