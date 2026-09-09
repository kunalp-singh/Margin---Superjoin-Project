import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.app.db.session import Base


def generate_uuid():
    return str(uuid.uuid4())


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    page_count = Column(Integer, default=0)
    status = Column(String, default="processing")  # processing, done, failed
    error_message = Column(Text, nullable=True)
    pipeline_version = Column(String, nullable=False, default="2.0")
    current_stage = Column(String, nullable=True, default="queued")
    stage_status = Column(JSON, nullable=False, default=dict)
    retry_count = Column(Integer, nullable=False, default=0)
    pipeline_started_at = Column(DateTime, nullable=True)
    pipeline_completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    facts = relationship("Fact", back_populates="document", cascade="all, delete-orphan")
    pipeline_runs = relationship("PipelineRun", back_populates="document", cascade="all, delete-orphan")


class Fact(Base):
    __tablename__ = "facts"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, nullable=False)
    source_quote = Column(Text, nullable=False)
    char_start = Column(Integer, default=0)
    char_end = Column(Integer, default=0)
    
    # Flexible JSON attributes: entity, metric, value, unit, period, scope, qualifier, etc.
    attributes = Column(JSON, nullable=False, default=dict)
    normalized_signature = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)  # List of floats
    
    status = Column(String, default="normal")  # normal, uncertain
    uncertainty_reason = Column(Text, nullable=True)
    pipeline_version = Column(String, nullable=False, default="2.0")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_facts_document_id", "document_id"),
        Index("ix_facts_signature", "normalized_signature"),
    )

    document = relationship("Document", back_populates="facts")
    
    relationships_as_a = relationship("Relationship", foreign_keys="Relationship.fact_a_id", back_populates="fact_a", cascade="all, delete-orphan")
    relationships_as_b = relationship("Relationship", foreign_keys="Relationship.fact_b_id", back_populates="fact_b", cascade="all, delete-orphan")


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(String, primary_key=True, default=generate_uuid)
    fact_a_id = Column(String, ForeignKey("facts.id", ondelete="CASCADE"), nullable=False)
    fact_b_id = Column(String, ForeignKey("facts.id", ondelete="CASCADE"), nullable=False)
    
    # Type: corroborated, contradicted, reconciled, uncertain
    type = Column(String, nullable=False)
    confidence = Column(Float, default=1.0)
    
    # JSON structured reasoning steps
    reasoning = Column(JSON, nullable=False, default=dict)
    pipeline_version = Column(String, nullable=False, default="2.0")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_relationships_fact_a_id", "fact_a_id"),
        Index("ix_relationships_fact_b_id", "fact_b_id"),
    )

    fact_a = relationship("Fact", foreign_keys=[fact_a_id], back_populates="relationships_as_a")
    fact_b = relationship("Fact", foreign_keys=[fact_b_id], back_populates="relationships_as_b")


class PipelineRun(Base):
    """Durable audit record for each processing/reprocessing attempt."""

    __tablename__ = "pipeline_runs"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    pipeline_version = Column(String, nullable=False, default="2.0")
    status = Column(String, nullable=False, default="queued")
    current_stage = Column(String, nullable=True)
    attempt = Column(Integer, nullable=False, default=1)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    document = relationship("Document", back_populates="pipeline_runs")
    stages = relationship("PipelineStage", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_pipeline_runs_document_id", "document_id"),)


class PipelineStage(Base):
    """Stage-level status used by the API timeline and safe retries."""

    __tablename__ = "pipeline_stages"

    id = Column(String, primary_key=True, default=generate_uuid)
    run_id = Column(String, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    detail = Column(JSON, nullable=False, default=dict)

    run = relationship("PipelineRun", back_populates="stages")

    __table_args__ = (
        Index("ix_pipeline_stages_run_id", "run_id"),
        Index("ix_pipeline_stages_name", "name"),
    )
