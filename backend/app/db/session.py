from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401  ensure models are registered

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    _ensure_hitl_columns()


def _ensure_hitl_columns() -> None:
    """Add human-review columns on databases created before the HITL fields existed."""
    statements = [
        "ALTER TABLE decision_runs ADD COLUMN IF NOT EXISTS review_status VARCHAR(32) DEFAULT 'pending_review'",
        "ALTER TABLE decision_runs ADD COLUMN IF NOT EXISTS human_feedback TEXT",
        "ALTER TABLE decision_runs ADD COLUMN IF NOT EXISTS human_constraints JSON",
        "ALTER TABLE decision_runs ADD COLUMN IF NOT EXISTS llm_warning TEXT",
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
