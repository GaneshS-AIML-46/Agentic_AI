"""
SYNTHETIC DATA — for demo only.
All catalogs, prices, capacities, orders, weather, and risk events are generated
with a fixed RNG seed so runs are reproducible. They are not real market data.
"""

from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Inventory,
    MarketPrice,
    Order,
    Product,
    RiskEvent,
    Route,
    Shipment,
    Supplier,
    SupplierProduct,
    Warehouse,
    WeatherEvent,
)

from app.core.paths import seed_dir

DATA_DIR = seed_dir()
RNG = random.Random(42)

# Catalog is authored, not invented at query time. Values stay in this module / CSVs.
PRODUCTS = [
    {"sku": "PROD-A", "name": "Product A", "category": "fasteners", "weight_kg": 0.45,
     "description": "Standard industrial fastener kit used in assembly lines."},
    {"sku": "PROD-B", "name": "Product B", "category": "electronics", "weight_kg": 1.2,
     "description": "Control-board module for warehouse automation."},
    {"sku": "PROD-C", "name": "Product C", "category": "packaging", "weight_kg": 0.2,
     "description": "Recyclable corrugated packaging bundle."},
    {"sku": "PROD-D", "name": "Product D", "category": "raw-metal", "weight_kg": 5.0,
     "description": "Cold-rolled steel blank."},
    {"sku": "PROD-E", "name": "Product E", "category": "plastics", "weight_kg": 0.8,
     "description": "Injection-molded housing."},
    {"sku": "PROD-F", "name": "Product F", "category": "chemicals", "weight_kg": 2.5,
     "description": "Industrial adhesive drum (unit = 1 kg equivalent)."},
    {"sku": "PROD-G", "name": "Product G", "category": "textiles", "weight_kg": 0.3,
     "description": "Protective work-glove pair."},
    {"sku": "PROD-H", "name": "Product H", "category": "electronics", "weight_kg": 0.15,
     "description": "IoT sensor node."},
    {"sku": "PROD-I", "name": "Product I", "category": "fasteners", "weight_kg": 0.6,
     "description": "High-tensile bolt set."},
    {"sku": "PROD-J", "name": "Product J", "category": "packaging", "weight_kg": 0.35,
     "description": "Pallet wrap film roll."},
]

SUPPLIERS = [
    {"code": "SUP-A", "name": "Tata Components", "country": "India", "city": "Pune",
     "latitude": 18.5204, "longitude": 73.8567, "reliability_score": 0.91, "risk_tier": "medium"},
    {"code": "SUP-B", "name": "Reliance Parts", "country": "India", "city": "Ahmedabad",
     "latitude": 23.0225, "longitude": 72.5714, "reliability_score": 0.96, "risk_tier": "low"},
    {"code": "SUP-C", "name": "Mahindra Precision", "country": "India", "city": "Nashik",
     "latitude": 20.0110, "longitude": 73.7903, "reliability_score": 0.88, "risk_tier": "medium"},
    {"code": "SUP-D", "name": "Delhi Metals", "country": "India", "city": "Delhi",
     "latitude": 28.6139, "longitude": 77.2090, "reliability_score": 0.90, "risk_tier": "medium"},
    {"code": "SUP-E", "name": "Bharat Forge", "country": "India", "city": "Kolkata",
     "latitude": 22.5726, "longitude": 88.3639, "reliability_score": 0.97, "risk_tier": "low"},
    {"code": "SUP-F", "name": "Godrej Fabrication", "country": "India", "city": "Hyderabad",
     "latitude": 17.3850, "longitude": 78.4867, "reliability_score": 0.94, "risk_tier": "low"},
    {"code": "SUP-G", "name": "Jindal Manufacturing", "country": "India", "city": "Surat",
     "latitude": 21.1702, "longitude": 72.8311, "reliability_score": 0.86, "risk_tier": "high"},
]

WAREHOUSES = [
    {"code": "WH-DEL", "name": "Delhi DC", "city": "Delhi", "country": "India",
     "latitude": 28.6139, "longitude": 77.2090, "capacity_units": 80000},
    {"code": "WH-BLR", "name": "Bangalore DC", "city": "Bangalore", "country": "India",
     "latitude": 12.9716, "longitude": 77.5946, "capacity_units": 60000},
    {"code": "WH-CHE", "name": "Chennai DC", "city": "Chennai", "country": "India",
     "latitude": 13.0827, "longitude": 80.2707, "capacity_units": 70000},
    {"code": "WH-MUM", "name": "Mumbai DC", "city": "Mumbai", "country": "India",
     "latitude": 19.076, "longitude": 72.877, "capacity_units": 50000},
]

# Product A offers are sized so combined monthly capacity > 10,000 (demo query).
SUPPLIER_PRODUCTS = [
    # Product A
    ("SUP-A", "PROD-A", 4.20, 5500, 18, 200),
    ("SUP-B", "PROD-A", 5.10, 4000, 12, 100),
    ("SUP-C", "PROD-A", 3.85, 7000, 22, 500),
    ("SUP-D", "PROD-A", 4.55, 3500, 16, 250),
    ("SUP-E", "PROD-A", 6.40, 2500, 8, 50),
    ("SUP-F", "PROD-A", 5.80, 3000, 10, 100),
    ("SUP-G", "PROD-A", 4.90, 2000, 14, 200),
    # Other products (subset of suppliers)
    ("SUP-A", "PROD-B", 42.0, 800, 20, 20),
    ("SUP-E", "PROD-B", 55.0, 600, 9, 10),
    ("SUP-F", "PROD-B", 49.5, 700, 11, 15),
    ("SUP-C", "PROD-C", 1.10, 12000, 25, 1000),
    ("SUP-G", "PROD-C", 1.35, 8000, 16, 500),
    ("SUP-D", "PROD-D", 18.4, 4000, 15, 100),
    ("SUP-E", "PROD-D", 22.1, 2500, 7, 50),
    ("SUP-A", "PROD-E", 7.80, 3000, 19, 200),
    ("SUP-C", "PROD-E", 6.90, 4500, 21, 300),
    ("SUP-G", "PROD-F", 12.5, 1500, 13, 50),
    ("SUP-E", "PROD-F", 15.2, 900, 8, 20),
    ("SUP-D", "PROD-G", 3.40, 6000, 17, 400),
    ("SUP-B", "PROD-G", 3.90, 4000, 11, 200),
    ("SUP-F", "PROD-H", 28.0, 1200, 10, 25),
    ("SUP-B", "PROD-H", 31.5, 900, 12, 20),
    ("SUP-E", "PROD-I", 8.20, 2000, 8, 80),
    ("SUP-A", "PROD-I", 6.75, 2800, 18, 150),
    ("SUP-C", "PROD-J", 2.15, 9000, 24, 800),
    ("SUP-G", "PROD-J", 2.40, 5000, 15, 400),
]

ROUTES = [
    # code, supplier, warehouse, mode, km, hours, cost_per_unit, capacity, fuel_factor, status
    ("RT-A-CHE-RL", "SUP-A", "WH-CHE", "rail", 1200, 36, 0.42, 8000, 1.05, "open"),
    ("RT-A-DEL-TR", "SUP-A", "WH-DEL", "truck", 1400, 48, 0.95, 6000, 1.10, "open"),
    ("RT-B-DEL-TR", "SUP-B", "WH-DEL", "truck", 900, 18, 0.55, 3500, 1.20, "open"),
    ("RT-B-BLR-RL", "SUP-B", "WH-BLR", "rail", 1500, 40, 0.88, 4000, 1.08, "open"),
    ("RT-C-CHE-TR", "SUP-C", "WH-CHE", "truck", 1300, 30, 0.38, 9000, 1.06, "open"),
    ("RT-C-DEL-RL", "SUP-C", "WH-DEL", "rail", 1200, 32, 1.05, 7000, 1.12, "open"),
    ("RT-C-MUM-TR", "SUP-C", "WH-MUM", "truck", 160, 4, 0.50, 5000, 1.07, "open"),
    ("RT-D-MUM-RL", "SUP-D", "WH-MUM", "rail", 1400, 36, 0.48, 4000, 1.15, "open"),
    ("RT-D-CHE-TR", "SUP-D", "WH-CHE", "truck", 2100, 60, 0.52, 4500, 1.08, "open"),
    ("RT-E-DEL-TR", "SUP-E", "WH-DEL", "truck", 1500, 40, 0.70, 3000, 1.18, "open"),
    ("RT-E-BLR-AIR", "SUP-E", "WH-BLR", "air", 1800, 4, 2.40, 800, 1.30, "open"),
    ("RT-F-BLR-TR", "SUP-F", "WH-BLR", "truck", 570, 10, 0.22, 5000, 1.10, "open"),
    ("RT-F-DEL-RL", "SUP-F", "WH-DEL", "rail", 1500, 40, 0.80, 3500, 1.09, "open"),
    ("RT-G-MUM-TR", "SUP-G", "WH-MUM", "truck", 280, 6, 0.46, 3000, 1.14, "open"),
    ("RT-G-CHE-RL", "SUP-G", "WH-CHE", "rail", 1200, 30, 0.60, 3500, 1.11, "open"),
    ("RT-G-DEL-TR", "SUP-G", "WH-DEL", "truck", 1100, 24, 0.92, 2500, 1.16, "open"),
]

INVENTORY_A = {
    "WH-DEL": (400, 80, 700, 500, 0.12),
    "WH-BLR": (250, 40, 500, 350, 0.14),
    "WH-CHE": (500, 60, 800, 600, 0.11),
    "WH-MUM": (200, 30, 450, 300, 0.10),
}

BASE_MONTHLY_DEMAND = {
    "PROD-A": 9200,
    "PROD-B": 420,
    "PROD-C": 6400,
    "PROD-D": 1800,
    "PROD-E": 2100,
    "PROD-F": 380,
    "PROD-G": 3100,
    "PROD-H": 540,
    "PROD-I": 1600,
    "PROD-J": 4200,
}


def _write_csv(name: str, rows: list[dict], fieldnames: list[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / name
    with path.open("w", newline="", encoding="utf-8") as f:
        f.write("# SYNTHETIC DATA — for demo only. Not real commercial data.\n")
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate_order_rows(months: int = 24) -> list[dict]:
    """Seasonal synthetic orders. Peak around Q4 for Product A."""
    today = date.today().replace(day=1)
    rows: list[dict] = []
    oid = 1
    for m in range(months, 0, -1):
        month_start = (today - timedelta(days=m * 30)).replace(day=1)
        season = 1 + 0.18 * math.sin(2 * math.pi * (month_start.month - 3) / 12)
        for sku, base in BASE_MONTHLY_DEMAND.items():
            monthly = int(base * season * (0.92 + RNG.random() * 0.16))
            remaining = monthly
            shares = [0.34, 0.22, 0.26, 0.18]
            codes = [w["code"] for w in WAREHOUSES]
            for idx, (wh, share) in enumerate(zip(codes, shares)):
                qty = remaining if idx == len(codes) - 1 else int(monthly * share)
                remaining -= 0 if idx == len(codes) - 1 else qty
                day = min(27, 3 + RNG.randint(0, 20))
                rows.append(
                    {
                        "id": oid,
                        "product_sku": sku,
                        "warehouse_code": wh,
                        "order_date": date(month_start.year, month_start.month, day).isoformat(),
                        "quantity": max(1, qty),
                        "channel": "wholesale",
                    }
                )
                oid += 1
    return rows


def export_csvs(order_rows: list[dict] | None = None) -> None:
    _write_csv("products.csv", PRODUCTS, list(PRODUCTS[0].keys()))
    _write_csv("suppliers.csv", SUPPLIERS, list(SUPPLIERS[0].keys()))
    _write_csv("warehouses.csv", WAREHOUSES, list(WAREHOUSES[0].keys()))
    sp_rows = [
        {
            "supplier_code": s,
            "product_sku": p,
            "unit_price": price,
            "monthly_capacity": cap,
            "lead_time_days": lead,
            "moq": moq,
        }
        for s, p, price, cap, lead, moq in SUPPLIER_PRODUCTS
    ]
    _write_csv("supplier_products.csv", sp_rows, list(sp_rows[0].keys()))
    rt_rows = [
        {
            "code": c,
            "supplier_code": s,
            "warehouse_code": w,
            "mode": mode,
            "distance_km": km,
            "transit_hours": hrs,
            "cost_per_unit": cost,
            "capacity_units": cap,
            "fuel_factor": fuel,
            "status": status,
        }
        for c, s, w, mode, km, hrs, cost, cap, fuel, status in ROUTES
    ]
    _write_csv("routes.csv", rt_rows, list(rt_rows[0].keys()))
    _write_csv(
        "orders.csv",
        order_rows if order_rows is not None else generate_order_rows(),
        ["id", "product_sku", "warehouse_code", "order_date", "quantity", "channel"],
    )


def seed_database(db: Session) -> dict[str, int]:
    existing = db.scalar(select(func.count(Product.id))) or 0
    if existing:
        return {"skipped": True, "products": existing}

    order_rows = generate_order_rows()
    export_csvs(order_rows)

    products: dict[str, Product] = {}
    for row in PRODUCTS:
        obj = Product(**row, unit="unit", is_synthetic=True)
        db.add(obj)
        db.flush()
        products[row["sku"]] = obj

    suppliers: dict[str, Supplier] = {}
    for row in SUPPLIERS:
        obj = Supplier(**row, status="active", is_synthetic=True)
        db.add(obj)
        db.flush()
        suppliers[row["code"]] = obj

    warehouses: dict[str, Warehouse] = {}
    for row in WAREHOUSES:
        obj = Warehouse(**row, is_synthetic=True)
        db.add(obj)
        db.flush()
        warehouses[row["code"]] = obj

    for s, p, price, cap, lead, moq in SUPPLIER_PRODUCTS:
        db.add(
            SupplierProduct(
                supplier_id=suppliers[s].id,
                product_id=products[p].id,
                unit_price=price,
                monthly_capacity=cap,
                lead_time_days=lead,
                moq=moq,
            )
        )

    routes: dict[str, Route] = {}
    for c, s, w, mode, km, hrs, cost, cap, fuel, status in ROUTES:
        obj = Route(
            code=c,
            supplier_id=suppliers[s].id,
            warehouse_id=warehouses[w].id,
            mode=mode,
            distance_km=km,
            transit_hours=hrs,
            cost_per_unit=cost,
            capacity_units=cap,
            fuel_factor=fuel,
            status=status,
            is_synthetic=True,
        )
        db.add(obj)
        db.flush()
        routes[c] = obj

    for sku, product in products.items():
        for wh_code, warehouse in warehouses.items():
            if sku == "PROD-A":
                on_hand, reserved, rop, ss, hold = INVENTORY_A[wh_code]
            else:
                base = BASE_MONTHLY_DEMAND[sku]
                on_hand = int(base * 0.08 * (0.7 + RNG.random() * 0.6))
                reserved = int(on_hand * 0.12)
                rop = int(base * 0.12)
                ss = int(base * 0.08)
                hold = round(0.08 + RNG.random() * 0.08, 3)
            db.add(
                Inventory(
                    warehouse_id=warehouse.id,
                    product_id=product.id,
                    on_hand=on_hand,
                    reserved=reserved,
                    reorder_point=rop,
                    safety_stock=ss,
                    holding_cost_per_unit=hold,
                )
            )

    for row in order_rows:
        db.add(
            Order(
                product_id=products[row["product_sku"]].id,
                warehouse_id=warehouses[row["warehouse_code"]].id,
                order_date=date.fromisoformat(row["order_date"]),
                quantity=row["quantity"],
                channel=row["channel"],
                is_synthetic=True,
            )
        )

    today = date.today()
    db.add_all(
        [
            Shipment(
                product_id=products["PROD-A"].id,
                supplier_id=suppliers["SUP-B"].id,
                warehouse_id=warehouses["WH-DEL"].id,
                route_id=routes["RT-B-DEL-TR"].id,
                quantity=900,
                ship_date=today - timedelta(days=18),
                eta=today - timedelta(days=16),
                status="delivered",
                actual_cost=900 * (5.10 + 0.55),
                is_synthetic=True,
            ),
            Shipment(
                product_id=products["PROD-A"].id,
                supplier_id=suppliers["SUP-C"].id,
                warehouse_id=warehouses["WH-CHE"].id,
                route_id=routes["RT-C-CHE-TR"].id,
                quantity=1400,
                ship_date=today - timedelta(days=40),
                eta=today - timedelta(days=32),
                status="delivered",
                actual_cost=1400 * (3.85 + 0.38),
                is_synthetic=True,
            ),

        ]
    )

    db.add_all(
        [
            RiskEvent(
                event_type="weather",
                severity="high",
                location="Bay of Bengal / East Coast",
                start_date=today - timedelta(days=3),
                end_date=today + timedelta(days=10),
                impact_description="Cyclone warning increasing transit variance for East Coast lanes.",
                affected_supplier_id=suppliers["SUP-E"].id,
                affected_route_id=routes["RT-E-DEL-TR"].id,
                status="open",
            ),
            RiskEvent(
                event_type="highway_congestion",
                severity="medium",
                location="Mumbai-Delhi Highway",
                start_date=today - timedelta(days=12),
                end_date=today + timedelta(days=5),
                impact_description="Traffic delays 24-36 hours above baseline at major checkpoints.",
                affected_supplier_id=None,
                affected_route_id=routes["RT-D-MUM-RL"].id,
                status="open",
            ),
            RiskEvent(
                event_type="fuel_spike",
                severity="medium",
                location="global",
                start_date=today - timedelta(days=20),
                end_date=None,
                impact_description="Marine fuel index 11% above 90-day average; truck diesel 7% above.",
                affected_supplier_id=None,
                affected_route_id=None,
                status="open",
            ),
            RiskEvent(
                event_type="supplier_quality",
                severity="low",
                location="Jebel Ali",
                start_date=today - timedelta(days=45),
                end_date=today - timedelta(days=10),
                impact_description="Closed CAPA on dimensional variance at Gulf Manufacturing. Monitor only.",
                affected_supplier_id=suppliers["SUP-G"].id,
                status="closed",
            ),
        ]
    )

    db.add_all(
        [
            MarketPrice(metric="marine_fuel_index", value=612.0, unit="USD/mt", observed_at=today - timedelta(days=2), region="global"),
            MarketPrice(metric="marine_fuel_index", value=551.0, unit="USD/mt", observed_at=today - timedelta(days=90), region="global"),
            MarketPrice(metric="diesel_index", value=1.18, unit="USD/l", observed_at=today - timedelta(days=2), region="EU"),
            MarketPrice(metric="usd_cny", value=7.24, unit="fx", observed_at=today - timedelta(days=1), region="CN"),
        ]
    )

    db.add_all(
        [
            WeatherEvent(
                region="South China Sea",
                event_type="typhoon",
                severity="high",
                start_date=today - timedelta(days=3),
                end_date=today + timedelta(days=8),
                disruption_factor=1.35,
            ),
            WeatherEvent(
                region="US Midwest",
                event_type="winter_storm",
                severity="low",
                start_date=today + timedelta(days=20),
                end_date=today + timedelta(days=23),
                disruption_factor=1.10,
            ),
        ]
    )

    db.commit()
    return {
        "skipped": False,
        "products": len(products),
        "suppliers": len(suppliers),
        "warehouses": len(warehouses),
        "routes": len(routes),
    }


def seed_if_empty(db: Session) -> dict:
    return seed_database(db)


if __name__ == "__main__":
    from app.db.session import SessionLocal, init_db

    init_db()
    _db = SessionLocal()
    try:
        print(seed_database(_db))
    finally:
        _db.close()
