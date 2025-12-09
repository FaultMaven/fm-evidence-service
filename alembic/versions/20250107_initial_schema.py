"""Initial schema for evidence table

Revision ID: 001_initial
Revises:
Create Date: 2025-01-07 00:00:00.000000

NOTE: storage_path column is Text (not VARCHAR(255)) to support long S3 signed URLs.
Local paths: /data/uploads/file.pdf (short)
S3 URLs: https://bucket.s3.region.amazonaws.com/key?X-Amz-Signature=... (can exceed 1024 chars)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create evidence table for file metadata."""
    op.create_table(
        'evidence',
        sa.Column('evidence_id', sa.String(length=36), nullable=False),
        sa.Column('case_id', sa.String(length=100), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_type', sa.String(length=100), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('storage_path', sa.Text(), nullable=False),  # Text for long S3 URLs
        sa.Column('evidence_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('evidence_metadata', sa.JSON(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.Column('uploaded_by', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('evidence_id')
    )

    # Create indexes for performance
    op.create_index(op.f('ix_evidence_evidence_id'), 'evidence', ['evidence_id'], unique=False)
    op.create_index(op.f('ix_evidence_case_id'), 'evidence', ['case_id'], unique=False)
    op.create_index(op.f('ix_evidence_evidence_type'), 'evidence', ['evidence_type'], unique=False)
    op.create_index(op.f('ix_evidence_uploaded_at'), 'evidence', ['uploaded_at'], unique=False)


def downgrade() -> None:
    """Drop evidence table."""
    op.drop_index(op.f('ix_evidence_uploaded_at'), table_name='evidence')
    op.drop_index(op.f('ix_evidence_evidence_type'), table_name='evidence')
    op.drop_index(op.f('ix_evidence_case_id'), table_name='evidence')
    op.drop_index(op.f('ix_evidence_evidence_id'), table_name='evidence')
    op.drop_table('evidence')
