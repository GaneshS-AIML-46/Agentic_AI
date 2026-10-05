from __future__ import annotations

import hashlib
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Inventory, MarketPrice, Product, Route, Supplier, SupplierProduct, Warehouse

PRODUCT_SKU = "PROD-A"


def minute_key(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M")


def tick_steps(key: str) -> tuple[float, int]:
    """Small deterministic fuel and stock moves for one clock minute."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    fuel_step = round(((digest[0] % 11) - 5) * 0.4, 2)
    stock_step = (digest[1] % 21) - 10
    return fuel_step, stock_step


def advance(fuel: float, stock: int, key: str, applied_key: str | None) -> tuple[float, int, str, bool]:
    """Apply one minute at most once. Returns fuel, stock, applied minute, and whether it moved."""
    if applied_key == key:
        return fuel, stock, applied_key, False
    fuel_step, stock_step = tick_steps(key)
    return round(fuel + fuel_step, 2), stock + stock_step, key, True


def _latest_fuel(db: Session) -> MarketPrice | None:
    return db.scalar(
        select(MarketPrice)
        .where(MarketPrice.metric == "marine_fuel_index")
        .order_by(MarketPrice.observed_at.desc(), MarketPrice.id.desc())
    )


def _baseline_fuel(db: Session) -> float:
    oldest = db.scalar(
        select(MarketPrice)
        .where(MarketPrice.metric == "marine_fuel_index")
        .order_by(MarketPrice.observed_at.asc(), MarketPrice.id.asc())
    )
    if oldest is None or not oldest.value:
        return 1.0
    return float(oldest.value)


def fuel_multiplier(db: Session) -> float:
    latest = _latest_fuel(db)
    baseline = _baseline_fuel(db)
    if latest is None or baseline <= 0:
        return 1.0
    return round(float(latest.value) / baseline, 4)


def _product_a_stock(db: Session) -> int:
    product = db.scalar(select(Product).where(Product.sku == PRODUCT_SKU))
    if product is None:
        return 0
    rows = list(db.scalars(select(Inventory).where(Inventory.product_id == product.id)))
    return sum(row.on_hand for row in rows)


def snapshot(db: Session, applied: bool = False) -> dict:
    latest = _latest_fuel(db)
    return {
        "data_as_of": datetime.now().isoformat(timespec="seconds"),
        "fuel_index": None if latest is None else float(latest.value),
        "fuel_multiplier": fuel_multiplier(db),
        "product_a_on_hand": _product_a_stock(db),
        "applied": applied,
    }


def tick(db: Session, moment: datetime | None = None) -> dict:
    moment = moment or datetime.now()
    key = minute_key(moment)
    region = f"live:{key}"
    already = db.scalar(
        select(MarketPrice).where(
            MarketPrice.metric == "marine_fuel_index",
            MarketPrice.region == region,
        )
    )
    if already is not None:
        return snapshot(db, applied=False)

    latest = _latest_fuel(db)
    current = float(latest.value) if latest is not None else 612.0
    stock = _product_a_stock(db)
    fuel, _stock, _key, moved = advance(current, stock, key, None)
    db.add(
        MarketPrice(
            metric="marine_fuel_index",
            value=fuel,
            unit="USD/mt",
            observed_at=date.today(),
            region=region,
            is_synthetic=True,
        )
    )
    product = db.scalar(select(Product).where(Product.sku == PRODUCT_SKU))
    if product is not None and moved:
        _step_fuel, stock_step = tick_steps(key)
        for row in db.scalars(select(Inventory).where(Inventory.product_id == product.id)):
            row.on_hand = max(row.reserved, row.on_hand + stock_step)
    db.commit()
    return snapshot(db, applied=True)


def apply_edit(
    db: Session,
    supplier_code: str | None = None,
    unit_price: float | None = None,
    warehouse_code: str | None = None,
    on_hand: int | None = None,
    route_code: str | None = None,
    route_status: str | None = None,
) -> dict:
    if unit_price is not None:
        if not supplier_code:
            raise ValueError("supplier_code is required when setting unit_price")
        if unit_price <= 0:
            raise ValueError("unit_price must be greater than zero")
        supplier = db.scalar(select(Supplier).where(Supplier.code == supplier_code))
        product = db.scalar(select(Product).where(Product.sku == PRODUCT_SKU))
        if supplier is None or product is None:
            raise ValueError(f"Unknown supplier or product for {supplier_code}")
        offer = db.scalar(
            select(SupplierProduct).where(
                SupplierProduct.supplier_id == supplier.id,
                SupplierProduct.product_id == product.id,
            )
        )
        if offer is None:
            raise ValueError(f"{supplier_code} does not supply {PRODUCT_SKU}")
        offer.unit_price = round(float(unit_price), 4)

    if on_hand is not None:
        if not warehouse_code:
            raise ValueError("warehouse_code is required when setting on_hand")
        if on_hand < 0:
            raise ValueError("on_hand cannot be negative")
        warehouse = db.scalar(select(Warehouse).where(Warehouse.code == warehouse_code))
        product = db.scalar(select(Product).where(Product.sku == PRODUCT_SKU))
        if warehouse is None or product is None:
            raise ValueError(f"Unknown warehouse {warehouse_code}")
        row = db.scalar(
            select(Inventory).where(
                Inventory.warehouse_id == warehouse.id,
                Inventory.product_id == product.id,
            )
        )
        if row is None:
            raise ValueError(f"No Product A stock at {warehouse_code}")
        row.on_hand = max(row.reserved, int(on_hand))

    if route_status is not None:
        if not route_code:
            raise ValueError("route_code is required when setting route_status")
        if route_status not in {"open", "disrupted"}:
            raise ValueError("route_status must be open or disrupted")
        route = db.scalar(select(Route).where(Route.code == route_code))
        if route is None:
            raise ValueError(f"Unknown route {route_code}")
        route.status = route_status

    db.commit()
    current = snapshot(db, applied=True)
    current["edit"] = {
        "supplier_code": supplier_code,
        "unit_price": unit_price,
        "warehouse_code": warehouse_code,
        "on_hand": on_hand,
        "route_code": route_code,
        "route_status": route_status,
    }
    return current
