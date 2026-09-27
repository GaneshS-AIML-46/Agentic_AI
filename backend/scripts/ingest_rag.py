"""Ingest markdown knowledge into pgvector + tsvector."""

from app.db.session import SessionLocal, init_db
from app.rag.ingest import ingest_knowledge


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        print(ingest_knowledge(db, force=True))
    finally:
        db.close()


if __name__ == "__main__":
    main()
