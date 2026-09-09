from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
from backend.app.schemas.fact import FactResponse


class RelationshipBase(BaseModel):
    fact_a_id: str
    fact_b_id: str
    type: str  # corroborated, contradicted, reconciled, uncertain
    confidence: float = 1.0
    reasoning: Dict[str, Any]
    pipeline_version: str = "2.0"


class RelationshipCreate(RelationshipBase):
    pass


class RelationshipResponse(RelationshipBase):
    id: str
    created_at: datetime
    fact_a: Optional[FactResponse] = None
    fact_b: Optional[FactResponse] = None

    class Config:
        from_attributes = True
