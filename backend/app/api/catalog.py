from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.repositories import list_products, list_suppliers, list_warehouses
from app.db.session import get_db

router = APIRouter()


@router.get("/catalog")
def catalog(db: Session = Depends(get_db)) -> dict:
    return {
        "products": [
            {"id": p.id, "sku": p.sku, "name": p.name, "category": p.category}
            for p in list_products(db)
        ],
        "suppliers": [
            {
                "id": s.id,
                "code": s.code,
                "name": s.name,
                "country": s.country,
                "reliability_score": s.reliability_score,
                "risk_tier": s.risk_tier,
            }
            for s in list_suppliers(db)
        ],
        "warehouses": [
            {"id": w.id, "code": w.code, "name": w.name, "city": w.city, "country": w.country}
            for w in list_warehouses(db)
        ],
        "data_disclaimer": "SYNTHETIC DATA — for demo only.",
    }
