from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.db.models import Fact, Document, Relationship
from backend.app.schemas.fact import FactResponse

router = APIRouter(prefix="/facts", tags=["facts"])


@router.get("", response_model=List[FactResponse])
def list_facts(
    status: Optional[str] = Query(None, description="Filter by status: normal or uncertain"),
    document_id: Optional[str] = Query(None, description="Filter by document_id"),
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type: corroborated, contradicted, reconciled, uncertain"),
    db: Session = Depends(get_db)
):
    query = db.query(Fact, Document.filename).join(Document, Fact.document_id == Document.id)

    if status:
        query = query.filter(Fact.status == status)
    if document_id:
        query = query.filter(Fact.document_id == document_id)
    if relationship_type:
        # Join relationships table
        query = query.filter(
            Fact.id.in_(
                db.query(Relationship.fact_a_id).filter(Relationship.type == relationship_type)
                .union(db.query(Relationship.fact_b_id).filter(Relationship.type == relationship_type))
            )
        )

    results = query.all()
    resp = []
    for fact_obj, filename in results:
        resp.append(FactResponse(
            id=fact_obj.id,
            document_id=fact_obj.document_id,
            page_number=fact_obj.page_number,
            source_quote=fact_obj.source_quote,
            char_start=fact_obj.char_start,
            char_end=fact_obj.char_end,
            attributes=fact_obj.attributes,
            normalized_signature=fact_obj.normalized_signature,
            status=fact_obj.status,
            uncertainty_reason=fact_obj.uncertainty_reason,
            pipeline_version=fact_obj.pipeline_version,
            created_at=fact_obj.created_at,
            document_filename=filename
        ))
    return resp


@router.get("/{fact_id}", response_model=FactResponse)
def get_fact(fact_id: str, db: Session = Depends(get_db)):
    result = db.query(Fact, Document.filename).join(Document, Fact.document_id == Document.id).filter(Fact.id == fact_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Fact not found.")
    
    fact_obj, filename = result
    return FactResponse(
        id=fact_obj.id,
        document_id=fact_obj.document_id,
        page_number=fact_obj.page_number,
        source_quote=fact_obj.source_quote,
        char_start=fact_obj.char_start,
        char_end=fact_obj.char_end,
        attributes=fact_obj.attributes,
        normalized_signature=fact_obj.normalized_signature,
        status=fact_obj.status,
        uncertainty_reason=fact_obj.uncertainty_reason,
        pipeline_version=fact_obj.pipeline_version,
        created_at=fact_obj.created_at,
        document_filename=filename
    )
