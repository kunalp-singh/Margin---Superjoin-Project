import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.db.session import engine, Base, ensure_runtime_indexes, run_additive_migrations
from backend.app.api import documents, facts, relationships, review

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)
run_additive_migrations()
ensure_runtime_indexes()

app = FastAPI(
    title="Margin API — Fact Knowledge Layer",
    description="Backend API for document ingestion, fact extraction, grounding, and relationship reasoning.",
    version="1.0.0"
)

# CORS configuration for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(documents.router, prefix="/api")
app.include_router(facts.router, prefix="/api")
app.include_router(relationships.router, prefix="/api")
app.include_router(review.router, prefix="/api")


@app.get("/")
def root():
    return {
        "app": "Margin",
        "status": "online",
        "docs": "/docs",
        "description": "Fact Knowledge Layer API"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
