from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.provenance import EvidenceHit
from app.rag.embed import embed_texts


def _rrf(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


def _overlap(query: str, body: str) -> float:
    q = {w for w in query.lower().split() if len(w) > 2}
    if not q:
        return 0.0
    b = set(body.lower().split())
    return len(q & b) / len(q)


def search(db: Session, query: str, k: int = 6) -> list[EvidenceHit]:
    if not query.strip():
        return []

    vector = embed_texts([query], task_type="RETRIEVAL_QUERY")[0]
    vec_literal = "[" + ",".join(f"{x:.6f}" for x in vector) + "]"

    dense_sql = text(
        """
        SELECT c.id, c.content, d.title, d.source_path, d.doc_type,
               1 - (c.embedding <=> CAST(:vec AS vector)) AS score
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        ORDER BY c.embedding <=> CAST(:vec AS vector)
        LIMIT :lim
        """
    )
    sparse_sql = text(
        """
        SELECT c.id, c.content, d.title, d.source_path, d.doc_type,
               ts_rank(c.tsv, plainto_tsquery('english', :q)) AS score
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.tsv @@ plainto_tsquery('english', :q)
        ORDER BY score DESC
        LIMIT :lim
        """
    )

    dense_rows = db.execute(dense_sql, {"vec": vec_literal, "lim": 12}).mappings().all()
    sparse_rows = db.execute(sparse_sql, {"q": query, "lim": 12}).mappings().all()

    fused: dict[int, dict] = {}
    for rank, row in enumerate(dense_rows, start=1):
        item = fused.setdefault(row["id"], {**dict(row), "rrf": 0.0})
        item["rrf"] += _rrf(rank)
    for rank, row in enumerate(sparse_rows, start=1):
        item = fused.setdefault(row["id"], {**dict(row), "rrf": 0.0})
        item["rrf"] += _rrf(rank)

    ranked = sorted(
        fused.values(),
        key=lambda r: r["rrf"] + 0.15 * _overlap(query, r["content"]),
        reverse=True,
    )[:k]

    return [
        EvidenceHit(
            document_id=str(r["id"]),
            title=r["title"],
            snippet=r["content"][:420],
            score=round(float(r["rrf"]), 4),
            source_path=r.get("source_path"),
            doc_type=r.get("doc_type"),
        )
        for r in ranked
    ]
