from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Inventory,
    MarketPrice,
    Order,
    Product,
    RiskEvent,
    Route,
    Supplier,
    SupplierProduct,
    Warehouse,
    WeatherEvent,
)


def resolve_product(db: Session, query: str) -> Product | None:
    q = query.strip()
    product = db.scalar(select(Product).where(Product.name.ilike(q)))
    if product:
        return product
    product = db.scalar(select(Product).where(Product.sku.ilike(q)))
    if product:
        return product
    return db.scalar(select(Product).where(Product.name.ilike(f"%{q}%")))


def monthly_order_history(db: Session, product_id: int, months: int = 24) -> list[dict]:
    cutoff = date.today().replace(day=1) - timedelta(days=months * 31)
    stmt = (
        select(
            func.date_trunc("month", Order.order_date).label("month"),
            func.sum(Order.quantity).label("qty"),
        )
        .where(Order.product_id == product_id, Order.order_date >= cutoff)
        .group_by("month")
        .order_by("month")
    )
    rows = db.execute(stmt).all()
    return [{"month": r.month.date().isoformat(), "quantity": int(r.qty)} for r in rows]


def supplier_offers(db: Session, product_id: int) -> list[SupplierProduct]:
    return list(
        db.scalars(
            select(SupplierProduct)
            .options(joinedload(SupplierProduct.supplier))
            .where(SupplierProduct.product_id == product_id)
        ).unique()
    )


def inventory_for_product(db: Session, product_id: int) -> list[Inventory]:
    return list(
        db.scalars(
            select(Inventory)
            .options(joinedload(Inventory.warehouse))
            .where(Inventory.product_id == product_id)
        ).unique()
    )


def routes_for_suppliers(db: Session, supplier_ids: list[int]) -> list[Route]:
    if not supplier_ids:
        return []
    return list(
        db.scalars(
            select(Route)
            .options(joinedload(Route.supplier), joinedload(Route.warehouse))
            .where(Route.supplier_id.in_(supplier_ids))
        ).unique()
    )


def open_risk_events(db: Session) -> list[RiskEvent]:
    return list(db.scalars(select(RiskEvent).where(RiskEvent.status == "open")))


def latest_market_prices(db: Session) -> list[MarketPrice]:
    return list(
        db.scalars(
            select(MarketPrice).order_by(MarketPrice.observed_at.desc(), MarketPrice.id.desc()).limit(40)
        )
    )


def weather_events(db: Session) -> list[WeatherEvent]:
    return list(db.scalars(select(WeatherEvent)))


def list_products(db: Session) -> list[Product]:
    return list(db.scalars(select(Product).order_by(Product.sku)))


def list_suppliers(db: Session) -> list[Supplier]:
    return list(db.scalars(select(Supplier).order_by(Supplier.code)))


def list_warehouses(db: Session) -> list[Warehouse]:
    return list(db.scalars(select(Warehouse).order_by(Warehouse.code)))
