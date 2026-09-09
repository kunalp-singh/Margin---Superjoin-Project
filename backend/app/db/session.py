from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def run_additive_migrations():
    """Apply idempotent, additive migrations to existing SQLite databases.

    ``create_all`` intentionally does not alter existing tables.  Keeping this
    tiny migration runner here avoids a destructive reset for demo databases
    while still allowing pipeline metadata to evolve.
    """
    if engine.dialect.name != "sqlite":
        return
    migrations = {
        "documents": {
            "pipeline_version": "VARCHAR DEFAULT '2.0'",
            "current_stage": "VARCHAR DEFAULT 'queued'",
            "stage_status": "JSON",
            "retry_count": "INTEGER DEFAULT 0",
            "pipeline_started_at": "DATETIME",
            "pipeline_completed_at": "DATETIME",
            "updated_at": "DATETIME",
        },
        "facts": {"pipeline_version": "VARCHAR DEFAULT '1.0'"},
        "relationships": {"pipeline_version": "VARCHAR DEFAULT '1.0'"},
    }
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version VARCHAR PRIMARY KEY, applied_at DATETIME NOT NULL)"
        ))
        for table_name, columns in migrations.items():
            existing = {row[1] for row in connection.execute(text(f"PRAGMA table_info({table_name})"))}
            for column, declaration in columns.items():
                if column not in existing:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column} {declaration}"))
            connection.execute(text(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) "
                "VALUES ('2.0-pipeline-status', CURRENT_TIMESTAMP)"
            ))
        connection.execute(text(
            "UPDATE documents SET pipeline_version = COALESCE(pipeline_version, '1.0'), "
            "current_stage = CASE WHEN status = 'done' THEN 'complete' "
            "WHEN status = 'failed' THEN 'complete' ELSE COALESCE(current_stage, status) END, "
            "retry_count = COALESCE(retry_count, 0), "
            "stage_status = CASE WHEN stage_status IS NULL OR stage_status = '{}' THEN "
            "'{\"parse\":{\"status\":\"done\"},\"extract\":{\"status\":\"done\"},"
            "\"verify\":{\"status\":\"done\"},\"persist\":{\"status\":\"done\"},"
            "\"match\":{\"status\":\"done\"},\"complete\":{\"status\": \"done\"}}' "
            "ELSE stage_status END"
        ))


def ensure_runtime_indexes():
    """Add indexes to databases created before the model indexes existed."""
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_facts_document_id ON facts (document_id)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_facts_signature ON facts (normalized_signature)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_relationships_fact_a_id ON relationships (fact_a_id)"
        ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_relationships_fact_b_id ON relationships (fact_b_id)"
        ))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
