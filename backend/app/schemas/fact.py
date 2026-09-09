from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class FactBase(BaseModel):
    document_id: str
    page_number: int
    source_quote: str
    char_start: int = 0
    char_end: int = 0
    attributes: Dict[str, Any]
    normalized_signature: str
    status: str = "normal"
    uncertainty_reason: Optional[str] = None
    pipeline_version: str = "2.0"


class FactCreate(FactBase):
    embedding: Optional[List[float]] = None


class FactResponse(FactBase):
    id: str
    created_at: datetime
    document_filename: Optional[str] = None

    class Config:
        from_attributes = True
