from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.provenance import EvidenceHit, Provenanced


class DemandResult(BaseModel):
    product_id: int
    product_sku: str
    product_name: str
    requested_quantity: int | None
    forecast_units: int
    forecast_method: str
    history_months: int
    history: list[dict]
    demand_to_meet: int
    notes: list[str] = Field(default_factory=list)
    provenance: dict[str, Provenanced] = Field(default_factory=dict)


class SupplierOffer(BaseModel):
    supplier_id: int
    supplier_code: str
    supplier_name: str
    unit_price: float
    monthly_capacity: int
    lead_time_days: int
    moq: int
    reliability_score: float
    risk_tier: str
    status: str
    eligible: bool = True
    reasons: list[str] = Field(default_factory=list)


class SupplierResult(BaseModel):
    offers: list[SupplierOffer]
    notes: list[str] = Field(default_factory=list)


class RouteOption(BaseModel):
    route_id: int
    code: str
    supplier_id: int
    warehouse_id: int
    warehouse_code: str
    mode: str
    distance_km: float
    transit_hours: float
    cost_per_unit: float
    capacity_units: int
    fuel_factor: float
    status: str
    disrupted: bool = False
    effective_cost_per_unit: float


class RouteResult(BaseModel):
    routes: list[RouteOption]
    notes: list[str] = Field(default_factory=list)


class InventoryRow(BaseModel):
    warehouse_id: int
    warehouse_code: str
    on_hand: int
    reserved: int
    available: int
    reorder_point: int
    safety_stock: int
    holding_cost_per_unit: float
    capacity_units: int


class InventoryResult(BaseModel):
    rows: list[InventoryRow]
    total_available: int
    total_safety_stock: int
    net_requirement: int
    notes: list[str] = Field(default_factory=list)
    provenance: dict[str, Provenanced] = Field(default_factory=dict)


class RiskDriver(BaseModel):
    kind: str
    detail: str
    severity: str
    score_contribution: float


class RiskResult(BaseModel):
    score: float
    drivers: list[RiskDriver]
    fuel_multiplier: float = 1.0
    notes: list[str] = Field(default_factory=list)


class AgentBundle(BaseModel):
    demand: DemandResult
    suppliers: SupplierResult
    routes: RouteResult
    inventory: InventoryResult
    risk: RiskResult
    evidence: list[EvidenceHit] = Field(default_factory=list)
