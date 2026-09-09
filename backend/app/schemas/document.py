from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class DocumentBase(BaseModel):
    filename: str


class DocumentCreate(DocumentBase):
    pass


class DocumentResponse(DocumentBase):
    id: str
    uploaded_at: datetime
    page_count: int
    status: str
    error_message: Optional[str] = None
    fact_count: Optional[int] = 0
    pipeline_version: str = "2.0"
    current_stage: Optional[str] = None
    stage_status: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    pipeline_started_at: Optional[datetime] = None
    pipeline_completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PipelineStageResponse(BaseModel):
    name: str
    status: str
    attempts: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    detail: Dict[str, Any] = {}


class PipelineStatusResponse(BaseModel):
    document_id: str
    pipeline_version: str
    status: str
    current_stage: Optional[str] = None
    retry_count: int = 0
    error_message: Optional[str] = None
    stages: List[PipelineStageResponse] = Field(default_factory=list)
