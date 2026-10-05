export type DecisionResponse = {
  run_id: number;
  query: string;
  demand_forecast: {
    product?: string;
    sku?: string;
    forecast_units?: number;
    method?: string;
    history?: { month: string; quantity: number }[];
    requested_quantity?: number | null;
    demand_to_meet?: number;
  };
  supplier_allocation: { supplier_code: string; supplier_name: string; units: number; cost: number }[];
  routes: {
    supplier_code: string;
    warehouse_code: string;
    route_code: string;
    mode: string;
    quantity: number;
    line_cost: number;
    transit_hours: number;
    lead_time_days: number;
  }[];
  inventory_plan: {
    rows?: {
      warehouse_code: string;
      on_hand: number;
      reserved: number;
      available: number;
      safety_stock: number;
    }[];
    total_available?: number;
    net_requirement?: number;
  };
  total_cost: number | null;
  delivery_time_hours: number | null;
  risk_score: number | null;
  optimization_status: string | null;
  retrieved_evidence: { title: string; snippet: string; relevance?: string; score: number; source_path?: string }[];
  explainable_recommendation: {
    reason?: string;
    summary?: string;
    kpi_note?: string;
    allocation_note?: string;
    routes_note?: string;
    inventory_note?: string;
    writer?: string;
  };
  agent_trace: string[];
  validation: { ok?: boolean; issues?: string[] };
  what_if?: {
    label?: string;
    comparison?: Record<string, { baseline: number; scenario: number; delta: number }>;
  } | null;
  review_status?: string | null;
  human_feedback?: string | null;
  human_constraints?: { kind: string; code?: string | null; value?: number | null; raw?: string }[];
  llm_warning?: string | null;
  scenario?: { label?: string; narrative?: string } | null;
  data_as_of?: string | null;
  live?: {
    data_as_of?: string;
    fuel_index?: number | null;
    fuel_multiplier?: number;
    product_a_on_hand?: number;
    applied?: boolean;
  } | null;
  data_disclaimer: string;
};

const API = import.meta.env.VITE_API_BASE || "";

export async function createDecision(query: string): Promise<DecisionResponse> {
  const res = await fetch(`${API}/api/v1/decisions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function runWhatIf(body: {
  run_id: number;
  scenario: string;
  pct?: number;
  supplier_code?: string;
  route_code?: string;
  text?: string;
}): Promise<DecisionResponse> {
  const res = await fetch(`${API}/api/v1/what-if`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function reviewDecision(
  runId: number,
  action: "approve" | "revise",
  feedback = "",
): Promise<DecisionResponse> {
  const res = await fetch(`${API}/api/v1/decisions/${runId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, feedback }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export type LiveSnapshot = {
  data_as_of: string;
  fuel_index: number | null;
  fuel_multiplier: number;
  product_a_on_hand: number;
  applied: boolean;
};

export async function fetchLive(): Promise<LiveSnapshot> {
  const res = await fetch(`${API}/api/v1/live`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function saveLiveInputs(body: {
  supplier_code?: string;
  unit_price?: number;
  warehouse_code?: string;
  on_hand?: number;
  route_code?: string;
  route_status?: string;
}): Promise<LiveSnapshot> {
  const res = await fetch(`${API}/api/v1/live/inputs`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchCatalog() {
  const res = await fetch(`${API}/api/v1/catalog`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
