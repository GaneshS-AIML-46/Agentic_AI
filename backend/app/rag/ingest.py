from __future__ import annotations

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.paths import knowledge_dir
from app.db.models import Document, DocumentChunk
from app.rag.embed import embed_texts

KNOWLEDGE_DIR = knowledge_dir()


def chunk_text(text: str, size: int = 700, overlap: int = 80) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(0, end - overlap)
    return [c for c in chunks if c]


def _as_floats(value) -> list[float]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.strip().strip("[]")
        if not raw:
            return []
        return [float(part) for part in raw.split(",")]
    return [float(part) for part in value]


def embeddings_stale(db: Session) -> bool:
    """True when stored vectors do not match the current embedding function."""
    row = db.execute(
        text("SELECT content, embedding FROM document_chunks ORDER BY id LIMIT 1")
    ).mappings().first()
    if not row:
        return False
    stored = _as_floats(row["embedding"])
    fresh = embed_texts([row["content"]])[0]
    if len(stored) != len(fresh) or not stored:
        return True
    return sum(a * b for a, b in zip(stored, fresh)) < 0.85


def ingest_knowledge(db: Session, force: bool = False) -> dict:
    existing = db.scalar(select(func.count(Document.id))) or 0
    if existing and not force:
        try:
            stale = embeddings_stale(db)
        except Exception:
            stale = False
        if stale:
            force = True
        else:
            return {"skipped": True, "documents": existing}

    if force:
        db.execute(delete(DocumentChunk))
        db.execute(delete(Document))
        db.commit()

    files = sorted(KNOWLEDGE_DIR.glob("*.md"))
    n_chunks = 0
    for path in files:
        content = path.read_text(encoding="utf-8")
        title = path.stem.replace("_", " ").title()
        doc_type = path.stem.split("_")[0]
        doc = Document(
            title=title,
            source_path=str(path.as_posix()),
            doc_type=doc_type,
            content=content,
            is_synthetic=True,
        )
        db.add(doc)
        db.flush()
        parts = chunk_text(content)
        vectors = embed_texts(parts)
        for idx, (part, vec) in enumerate(zip(parts, vectors)):
            chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=idx,
                content=part,
                embedding=vec,
            )
            db.add(chunk)
            db.flush()
            db.execute(
                text(
                    "UPDATE document_chunks SET tsv = to_tsvector('english', :content) WHERE id = :id"
                ),
                {"content": part, "id": chunk.id},
            )
            n_chunks += 1
    db.commit()
    return {"skipped": False, "documents": len(files), "chunks": n_chunks}
