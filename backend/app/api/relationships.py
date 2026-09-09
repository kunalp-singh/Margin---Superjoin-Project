from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.db.models import Relationship, Fact, Document
from backend.app.schemas.relationship import RelationshipResponse
from backend.app.schemas.fact import FactResponse

router = APIRouter(prefix="/relationships", tags=["relationships"])


def build_fact_response(fact: Fact, db: Session) -> FactResponse:
    doc = db.query(Document).filter(Document.id == fact.document_id).first()
    return FactResponse(
        id=fact.id,
        document_id=fact.document_id,
        page_number=fact.page_number,
        source_quote=fact.source_quote,
        char_start=fact.char_start,
        char_end=fact.char_end,
        attributes=fact.attributes,
        normalized_signature=fact.normalized_signature,
        status=fact.status,
        uncertainty_reason=fact.uncertainty_reason,
        pipeline_version=fact.pipeline_version,
        created_at=fact.created_at,
        document_filename=doc.filename if doc else None
    )


@router.get("", response_model=List[RelationshipResponse])
def list_relationships(
    type: Optional[str] = Query(None, description="Filter by type: corroborated, contradicted, reconciled, uncertain"),
    db: Session = Depends(get_db)
):
    query = db.query(Relationship)
    if type:
        query = query.filter(Relationship.type == type)

    rels = query.all()
    results = []
    for rel in rels:
        fact_a = db.query(Fact).filter(Fact.id == rel.fact_a_id).first()
        fact_b = db.query(Fact).filter(Fact.id == rel.fact_b_id).first()
        results.append(RelationshipResponse(
            id=rel.id,
            fact_a_id=rel.fact_a_id,
            fact_b_id=rel.fact_b_id,
            type=rel.type,
            confidence=rel.confidence,
            reasoning=rel.reasoning,
            pipeline_version=rel.pipeline_version,
            created_at=rel.created_at,
            fact_a=build_fact_response(fact_a, db) if fact_a else None,
            fact_b=build_fact_response(fact_b, db) if fact_b else None
        ))
    return results


@router.get("/{relationship_id}", response_model=RelationshipResponse)
def get_relationship(relationship_id: str, db: Session = Depends(get_db)):
    rel = db.query(Relationship).filter(Relationship.id == relationship_id).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found.")

    fact_a = db.query(Fact).filter(Fact.id == rel.fact_a_id).first()
    fact_b = db.query(Fact).filter(Fact.id == rel.fact_b_id).first()

    return RelationshipResponse(
        id=rel.id,
        fact_a_id=rel.fact_a_id,
        fact_b_id=rel.fact_b_id,
        type=rel.type,
        confidence=rel.confidence,
        reasoning=rel.reasoning,
        pipeline_version=rel.pipeline_version,
        created_at=rel.created_at,
        fact_a=build_fact_response(fact_a, db) if fact_a else None,
        fact_b=build_fact_response(fact_b, db) if fact_b else None
    )
