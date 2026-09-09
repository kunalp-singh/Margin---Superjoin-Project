import os
import shutil
import uuid
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from backend.app.db.session import get_db, SessionLocal
from backend.app.db.models import Document, Fact, Relationship, PipelineRun
from backend.app.schemas.document import DocumentResponse, PipelineStatusResponse, PipelineStageResponse
from backend.app.services.pipeline import process_document_pipeline
from backend.app.config import DATA_DIR

router = APIRouter(prefix="/documents", tags=["documents"])
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)


def run_pipeline_in_background(document_id: str):
    """Background task handler with isolated database session."""
    db = SessionLocal()
    try:
        process_document_pipeline(document_id, db)
    finally:
        db.close()


def _document_response(doc: Document, db: Session) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        uploaded_at=doc.uploaded_at,
        page_count=doc.page_count,
        status=doc.status,
        error_message=doc.error_message,
        fact_count=db.query(Fact).filter(Fact.document_id == doc.id).count(),
        pipeline_version=doc.pipeline_version,
        current_stage=doc.current_stage,
        stage_status=doc.stage_status or {},
        retry_count=doc.retry_count or 0,
        pipeline_started_at=doc.pipeline_started_at,
        pipeline_completed_at=doc.pipeline_completed_at,
    )


@router.post("", response_model=DocumentResponse)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    doc_id = str(uuid.uuid4())
    safe_filename = f"{doc_id}_{file.filename}"
    file_path = str(UPLOADS_DIR / safe_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    doc = Document(
        id=doc_id,
        filename=file.filename,
        file_path=file_path,
        status="processing"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Launch background processing pipeline with dedicated DB session
    background_tasks.add_task(run_pipeline_in_background, doc.id)

    return _document_response(doc, db)


@router.get("", response_model=List[DocumentResponse])
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).all()
    results = []
    for doc in docs:
        fact_count = db.query(Fact).filter(Fact.document_id == doc.id).count()
        results.append(_document_response(doc, db))
    return results


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    fact_count = db.query(Fact).filter(Fact.document_id == doc.id).count()
    return _document_response(doc, db)


@router.get("/{document_id}/pipeline", response_model=PipelineStatusResponse)
@router.get("/{document_id}/status", response_model=PipelineStatusResponse, include_in_schema=False)
def get_pipeline_status(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    run = db.query(PipelineRun).filter(PipelineRun.document_id == document_id).order_by(PipelineRun.started_at.desc()).first()
    stages = [
        PipelineStageResponse(
            name=stage.name,
            status=stage.status,
            attempts=stage.attempts,
            started_at=stage.started_at,
            completed_at=stage.completed_at,
            error_message=stage.error_message,
            detail=stage.detail or {},
        )
        for stage in (run.stages if run else [])
    ]
    if not stages:
        stages = [
            PipelineStageResponse(
                name=name,
                status=state.get("status", "pending"),
                attempts=state.get("attempts", 0),
                detail={"detail": state.get("detail")} if state.get("detail") else {},
            )
            for name, state in (doc.stage_status or {}).items()
        ]
    return PipelineStatusResponse(
        document_id=doc.id,
        pipeline_version=doc.pipeline_version,
        status=doc.status,
        current_stage=doc.current_stage,
        retry_count=doc.retry_count or 0,
        error_message=doc.error_message,
        stages=stages,
    )


@router.post("/{document_id}/reprocess", response_model=DocumentResponse)
def reprocess_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.status == "processing":
        raise HTTPException(status_code=409, detail="Document is already being processed.")
    fact_ids = [row[0] for row in db.query(Fact.id).filter(Fact.document_id == document_id).all()]
    if fact_ids:
        db.query(Relationship).filter(
            (Relationship.fact_a_id.in_(fact_ids)) | (Relationship.fact_b_id.in_(fact_ids))
        ).delete(synchronize_session="fetch")
        db.query(Fact).filter(Fact.document_id == document_id).delete(synchronize_session="fetch")
    doc.status = "processing"
    doc.current_stage = "queued"
    doc.error_message = None
    doc.stage_status = {}
    db.commit()
    background_tasks.add_task(run_pipeline_in_background, doc.id)
    return _document_response(doc, db)


@router.delete("/{document_id}")
def delete_document(document_id: str, db: Session = Depends(get_db)):
    """
    Delete a document and all derived knowledge (facts + relationships).

    Relationships are deleted first (both sides), then facts, then the document.
    The uploaded PDF file is removed from disk after the DB commit succeeds.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Safety: refuse deletion while the background pipeline may still be inserting facts
    if doc.status == "processing":
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a document while it is still being processed. Please wait until analysis completes."
        )

    # Collect all fact IDs belonging to this document
    fact_ids = [f.id for f in db.query(Fact.id).filter(Fact.document_id == document_id).all()]

    # Count relationships that involve any of those facts (either side)
    rel_count = 0
    if fact_ids:
        rel_count = (
            db.query(Relationship)
            .filter(
                (Relationship.fact_a_id.in_(fact_ids)) |
                (Relationship.fact_b_id.in_(fact_ids))
            )
            .count()
        )

        # Explicitly delete relationships on both sides before facts are removed
        db.query(Relationship).filter(
            (Relationship.fact_a_id.in_(fact_ids)) |
            (Relationship.fact_b_id.in_(fact_ids))
        ).delete(synchronize_session="fetch")

    fact_count = len(fact_ids)

    # Delete facts (SQLAlchemy cascade would also handle this, but be explicit)
    if fact_ids:
        db.query(Fact).filter(Fact.document_id == document_id).delete(synchronize_session="fetch")

    # Store file_path before deleting the record
    file_path = doc.file_path

    # Delete the document record
    db.delete(doc)
    db.commit()

    # Remove PDF from disk only after successful DB commit
    if file_path and os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except OSError:
            # File removal failure should not fail the API response
            pass

    return {
        "success": True,
        "deleted_document_id": document_id,
        "deleted_facts": fact_count,
        "deleted_relationships": rel_count,
    }
