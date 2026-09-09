from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.db.models import Relationship, Fact, Document
from backend.app.api.relationships import build_fact_response

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/cases")
def get_review_cases(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns one canonical example of each of the 4 cases required by the brief:
    1. corroborated (differently phrased corroboration across documents)
    2. contradicted (genuine conflict on identical metric, period, and scope)
    3. reconciled (apparent conflict explained by context / time period)
    4. uncertain (extraction or reasoning ambiguity handled honestly)
    """
    case_types = ["corroborated", "contradicted", "reconciled", "uncertain"]
    cases = {}

    for c_type in case_types:
        rel = db.query(Relationship).filter(Relationship.type == c_type).first()
        if rel:
            fact_a = db.query(Fact).filter(Fact.id == rel.fact_a_id).first()
            fact_b = db.query(Fact).filter(Fact.id == rel.fact_b_id).first()
            cases[c_type] = {
                "relationship_id": rel.id,
                "type": rel.type,
                "confidence": rel.confidence,
                "reasoning": rel.reasoning,
                "fact_a": build_fact_response(fact_a, db) if fact_a else None,
                "fact_b": build_fact_response(fact_b, db) if fact_b else None
            }
        else:
            # Check if there is an uncertain fact without a relationship edge for case 4
            if c_type == "uncertain":
                unc_fact = db.query(Fact).filter(Fact.status == "uncertain").first()
                if unc_fact:
                    attrs = unc_fact.attributes or {}
                    evidence_fields = sum(
                        bool(attrs.get(field))
                        for field in ("entity", "metric", "value", "unit", "period", "scope")
                    )
                    confidence = round(min(0.85, 0.25 + evidence_fields * 0.08), 2)
                    cases["uncertain"] = {
                        "relationship_id": None,
                        "type": "uncertain",
                        "confidence": confidence,
                        "reasoning": {
                            "summary": "Extraction marked as uncertain rather than creating a normalized fact due to ambiguous referents.",
                            "reasoning_steps": [
                                "Step 1: Scanned source statement for entity, metric, value, period.",
                                f"Step 2: Detected ambiguous clause: '{unc_fact.source_quote}'.",
                                f"Step 3: Reason: {unc_fact.uncertainty_reason}"
                            ]
                        },
                        "fact_a": build_fact_response(unc_fact, db),
                        "fact_b": None
                    }
                else:
                    cases[c_type] = None
            else:
                cases[c_type] = None

    return {
        "cases": cases,
        "available_counts": {
            "corroborated": db.query(Relationship).filter(Relationship.type == "corroborated").count(),
            "contradicted": db.query(Relationship).filter(Relationship.type == "contradicted").count(),
            "reconciled": db.query(Relationship).filter(Relationship.type == "reconciled").count(),
            "uncertain": db.query(Relationship).filter(Relationship.type == "uncertain").count() + db.query(Fact).filter(Fact.status == "uncertain").count()
        }
    }
