import logging
import re
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from backend.app.config import PIPELINE_VERSION
from backend.app.db.models import Document, Fact, PipelineRun, PipelineStage, Relationship
from backend.app.services.pdf_parser import parse_pdf
from backend.app.services.gemini_service import (
    extract_facts_from_statements,
    verify_extracted_facts,
)
from backend.app.services.embedder import generate_embedding, find_top_candidates, is_compatible_candidate
from backend.app.services.gemini_service import classify_fact_relationship

logger = logging.getLogger(__name__)

STAGES = ("parse", "extract", "verify", "persist", "match", "complete")


def _stage_snapshot(status: str, detail: str | None = None, **extra: Any) -> Dict[str, Any]:
    value: Dict[str, Any] = {"status": status, "updated_at": datetime.utcnow().isoformat()}
    if detail:
        value["detail"] = detail
    value.update(extra)
    return value


def _begin_stage(db: Session, doc: Document, run: PipelineRun, stage: PipelineStage) -> None:
    now = datetime.utcnow()
    stage.status = "running"
    stage.attempts = (stage.attempts or 0) + 1
    stage.started_at = now
    run.status = "processing"
    run.current_stage = stage.name
    doc.current_stage = stage.name
    statuses = dict(doc.stage_status or {})
    statuses[stage.name] = _stage_snapshot("running", attempts=stage.attempts)
    doc.stage_status = statuses
    db.commit()


def _finish_stage(db: Session, doc: Document, stage: PipelineStage, status: str = "done", detail: str | None = None) -> None:
    stage.status = status
    stage.completed_at = datetime.utcnow()
    stage.error_message = detail if status == "failed" else None
    statuses = dict(doc.stage_status or {})
    statuses[stage.name] = _stage_snapshot(status, detail, attempts=stage.attempts)
    doc.stage_status = statuses
    db.commit()


def _fact_dict(fact: Fact) -> Dict[str, Any]:
    return {
        "id": fact.id,
        "document_id": fact.document_id,
        "page_number": fact.page_number,
        "source_quote": fact.source_quote,
        "attributes": fact.attributes,
        "normalized_signature": fact.normalized_signature,
        "embedding": fact.embedding,
        "status": fact.status,
        "uncertainty_reason": fact.uncertainty_reason,
    }


def process_document_pipeline(document_id: str, db: Session) -> None:
    """Run each ingestion stage transactionally and expose durable progress."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc or not doc.file_path:
        logger.error("Document %s not found or missing file_path.", document_id)
        return

    run = PipelineRun(
        document_id=document_id,
        pipeline_version=PIPELINE_VERSION,
        status="queued",
        current_stage="queued",
        attempt=(doc.retry_count or 0) + 1,
    )
    db.add(run)
    db.flush()
    stage_rows = {name: PipelineStage(run_id=run.id, name=name) for name in STAGES}
    db.add_all(stage_rows.values())
    doc.status = "processing"
    doc.error_message = None
    doc.pipeline_version = PIPELINE_VERSION
    doc.pipeline_started_at = datetime.utcnow()
    doc.pipeline_completed_at = None
    doc.retry_count = run.attempt - 1
    doc.current_stage = "queued"
    doc.stage_status = {name: _stage_snapshot("pending") for name in STAGES}
    db.commit()

    parsed_data: Dict[str, Any] = {}
    extracted: List[Dict[str, Any]] = []
    new_facts: List[Fact] = []
    try:
        stage = stage_rows["parse"]
        _begin_stage(db, doc, run, stage)
        parsed_data = parse_pdf(doc.file_path)
        doc.page_count = parsed_data["page_count"]
        _finish_stage(db, doc, stage, detail=f"{parsed_data['page_count']} pages parsed")

        stage = stage_rows["extract"]
        _begin_stage(db, doc, run, stage)
        for page_data in parsed_data["pages"]:
            extracted.extend(extract_facts_from_statements(page_data["statements"], doc.filename))
        _finish_stage(db, doc, stage, detail=f"{len(extracted)} candidate facts")

        stage = stage_rows["verify"]
        _begin_stage(db, doc, run, stage)
        extracted = verify_extracted_facts(extracted, doc.filename)
        _finish_stage(db, doc, stage, detail=f"{len(extracted)} verified facts")

        stage = stage_rows["persist"]
        _begin_stage(db, doc, run, stage)
        for data in extracted:
            fact = Fact(
                document_id=doc.id,
                page_number=data["page_number"],
                source_quote=data["source_quote"],
                char_start=data["char_start"],
                char_end=data["char_end"],
                attributes=data["attributes"],
                normalized_signature=data["normalized_signature"],
                embedding=generate_embedding(data["normalized_signature"]),
                status=data["status"],
                uncertainty_reason=data.get("uncertainty_reason"),
                pipeline_version=PIPELINE_VERSION,
            )
            db.add(fact)
            db.flush()
            new_facts.append(fact)
        db.commit()
        _finish_stage(db, doc, stage, detail=f"{len(new_facts)} facts persisted")

        stage = stage_rows["match"]
        _begin_stage(db, doc, run, stage)
        existing = [
            _fact_dict(fact)
            for fact in db.query(Fact).filter(Fact.document_id != document_id, Fact.status == "normal").all()
        ]
        processed_pairs = set()
        for fact in new_facts:
            current = _fact_dict(fact)
            compatible_existing = [
                candidate for candidate in existing
                if is_compatible_candidate(current, candidate)
            ]
            for candidate, similarity in find_top_candidates(current, compatible_existing):
                pair = tuple(sorted((fact.id, candidate["id"])))
                if pair in processed_pairs:
                    continue
                processed_pairs.add(pair)
                classified = classify_fact_relationship(current, candidate)
                db.add(Relationship(
                    fact_a_id=fact.id,
                    fact_b_id=candidate["id"],
                    type=classified["relationship_type"],
                    confidence=classified.get("confidence", 0.0),
                    reasoning={
                        **(classified.get("reasoning") or {}),
                        "candidate_similarity": round(similarity, 4),
                    },
                    pipeline_version=PIPELINE_VERSION,
                ))
        db.commit()
        _finish_stage(db, doc, stage, detail=f"{len(processed_pairs)} compatible pairs classified")

        stage = stage_rows["complete"]
        _begin_stage(db, doc, run, stage)
        doc.status = "done"
        doc.current_stage = "complete"
        doc.pipeline_completed_at = datetime.utcnow()
        run.status = "done"
        run.current_stage = "complete"
        run.completed_at = datetime.utcnow()
        _finish_stage(db, doc, stage)
        db.commit()
        logger.info("Pipeline completed successfully for %s.", doc.filename)
    except Exception as exc:
        logger.error("Pipeline error for %s: %s", document_id, exc, exc_info=True)
        failed_stage = doc.current_stage or "unknown"
        if failed_stage in stage_rows:
            _finish_stage(db, doc, stage_rows[failed_stage], "failed", str(exc))
        doc.status = "failed"
        doc.error_message = str(exc)
        run.status = "failed"
        run.error_message = str(exc)
        run.completed_at = datetime.utcnow()
        db.commit()
