"""
Database Models

SQLAlchemy ORM models for evidence metadata storage.
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class EvidenceDB(Base):
    """Evidence metadata database model"""

    __tablename__ = "evidence"

    evidence_id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    case_id = Column(String(100), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    storage_path = Column(Text, nullable=False)
    evidence_type = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)
    evidence_metadata = Column(JSON, nullable=True)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    uploaded_by = Column(String(100), nullable=False)

    def __repr__(self):
        return f"<EvidenceDB(evidence_id='{self.evidence_id}', filename='{self.filename}')>"
