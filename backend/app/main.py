from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import SessionLocal, init_db
from app.rag.ingest import ingest_knowledge
from scripts.seed import seed_if_empty


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    init_db()
    db = SessionLocal()
    try:
        seed_if_empty(db)
        ingest_knowledge(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="SupplyChainAI",
    description="Multi-agent supply chain decision intelligence. SYNTHETIC demo data.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root():
    return {"name": "SupplyChainAI", "docs": "/docs", "health": "/api/v1/health"}
