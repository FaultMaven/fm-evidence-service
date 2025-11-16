"""
Evidence Service Settings

Configuration management using Pydantic settings with environment variable support.
"""

from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Evidence Service configuration"""

    # Service Configuration
    service_name: str = Field(default="fm-evidence-service", description="Service name")
    environment: str = Field(default="development", description="Environment (development, production)")
    port: int = Field(default=8004, description="Service port")
    host: str = Field(default="0.0.0.0", description="Service host")

    # Database Configuration
    database_url: str = Field(
        default="sqlite+aiosqlite:///./fm_evidence.db",
        description="Database connection URL"
    )

    # File Storage Configuration
    storage_type: str = Field(default="local", description="Storage type (local or s3)")
    local_upload_dir: str = Field(default="./uploads", description="Local upload directory")
    max_file_size_mb: int = Field(default=50, description="Maximum file size in MB")
    allowed_file_types: str = Field(
        default=".log,.txt,.png,.jpg,.jpeg,.pdf,.json",
        description="Allowed file extensions (comma-separated)"
    )

    # S3 Configuration (for production)
    s3_endpoint_url: Optional[str] = Field(
        default=None,
        description="S3/MinIO endpoint URL"
    )
    s3_bucket_name: str = Field(default="faultmaven-evidence", description="S3 bucket name")
    s3_access_key: Optional[str] = Field(default=None, description="S3 access key")
    s3_secret_key: Optional[str] = Field(default=None, description="S3 secret key")

    # Pagination
    default_page_size: int = Field(default=50, description="Default page size")
    max_page_size: int = Field(default=100, description="Maximum page size")

    # CORS Configuration
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8090"],
        description="Allowed CORS origins"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @property
    def max_file_size_bytes(self) -> int:
        """Convert max file size from MB to bytes"""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def allowed_extensions(self) -> List[str]:
        """Parse allowed file types into list"""
        return [ext.strip() for ext in self.allowed_file_types.split(",")]


# Global settings instance
settings = Settings()
