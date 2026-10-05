import { FormEvent, useEffect, useState } from "react";
import { createDecision, DecisionResponse, fetchCatalog, fetchLive, LiveSnapshot, reviewDecision, runWhatIf, saveLiveInputs } from "../api/client";
import ComparisonTable from "../components/ComparisonTable";
import HumanReviewPanel from "../components/HumanReviewPanel";
import KpiRow from "../components/KpiRow";
import StatusBadge from "../components/StatusBadge";

const EXAMPLE =
  "I need 10,000 units of Product A next month. Find the lowest-cost supply plan with low risk.";

function money(n: number | null | undefined) {
  if (n == null) return "—";
  return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export default function PlannerPage() {
  const [query, setQuery] = useState(EXAMPLE);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DecisionResponse | null>(null);
  const [catalog, setCatalog] = useState("");
  const [scenario, setScenario] = useState("supplier_failure");
  const [pct, setPct] = useState(20);
  const [supplierCode, setSupplierCode] = useState("SUP-C");
  const [nlScenario, setNlScenario] = useState("supplier SUP-C fails and fuel +15%");
  const [live, setLive] = useState<LiveSnapshot | null>(null);
  const [editSupplier, setEditSupplier] = useState("SUP-C");
  const [editPrice, setEditPrice] = useState("3.86");
  const [editWarehouse, setEditWarehouse] = useState("WH-DEL");
  const [editOnHand, setEditOnHand] = useState("");
  const [editRoute, setEditRoute] = useState("RT-C-CHE-TR");
  const [editRouteStatus, setEditRouteStatus] = useState("open");

  useEffect(() => {
    fetchCatalog()
      .then((c) => {
        const products = (c.products || []).map((p: { sku: string }) => p.sku).join(", ");
        setCatalog(products);
      })
      .catch(() => setCatalog("API not reachable yet"));
  }, []);

  useEffect(() => {
    const load = () => {
      fetchLive().then(setLive).catch(() => setLive(null));
    };
    load();
    const timer = window.setInterval(load, 60_000);
    return () => window.clearInterval(timer);
  }, []);

  async function run(action: () => Promise<DecisionResponse>) {
    setLoading(true);
    setError(null);
    try {
      setResult(await action());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void run(() => createDecision(query));
  }

  return (
    <div className="page">
      <header>
        <div>
          <p className="eyebrow">Optimize. Explain. Execute.</p>
          <h1>OptiChain</h1>
        </div>
      </header>

      <form className="panel" onSubmit={onSubmit}>
        <label htmlFor="query">Natural-language supply-chain problem</label>
        <textarea id="query" value={query} onChange={(e) => setQuery(e.target.value)} rows={4} />
        <div className="row">
          <button type="submit" disabled={loading}>
            {loading ? "Planning…" : "Optimize supply plan"}
          </button>
          <p className="hint">Catalog: {catalog || "loading…"}</p>
        </div>
      </form>

      <section className="panel">
        <h2>Live network</h2>
        <p className="hint">
          Fuel index {live?.fuel_index ?? "—"} · multiplier {live?.fuel_multiplier ?? "—"} · Product A on hand{" "}
          {live?.product_a_on_hand ?? "—"} · as of {live?.data_as_of ?? "waiting"}
        </p>
        <div className="row wrap">
          <input value={editSupplier} onChange={(e) => setEditSupplier(e.target.value)} title="Supplier code" />
          <input value={editPrice} onChange={(e) => setEditPrice(e.target.value)} title="Unit price" />
          <input value={editWarehouse} onChange={(e) => setEditWarehouse(e.target.value)} title="Warehouse code" />
          <input value={editOnHand} onChange={(e) => setEditOnHand(e.target.value)} title="On hand" placeholder="On hand" />
          <input value={editRoute} onChange={(e) => setEditRoute(e.target.value)} title="Route code" />
          <select value={editRouteStatus} onChange={(e) => setEditRouteStatus(e.target.value)}>
            <option value="open">Route open</option>
            <option value="disrupted">Route disrupted</option>
          </select>
          <button
            type="button"
            disabled={loading}
            onClick={() =>
              void run(async () => {
                const saved = await saveLiveInputs({
                  supplier_code: editSupplier,
                  unit_price: Number(editPrice),
                  warehouse_code: editWarehouse,
                  on_hand: editOnHand === "" ? undefined : Number(editOnHand),
                  route_code: editRoute,
                  route_status: editRouteStatus,
                });
                setLive(saved);
                return createDecision(query);
              })
            }
          >
            Save and replan
          </button>
        </div>
      </section>

      {error && <div className="error">{error}</div>}

      {result && (
        <>
          <div className="row">
            <StatusBadge status={result.review_status} />
            <StatusBadge status={result.optimization_status} />
            <p className="hint">
              Data as of {result.data_as_of || result.live?.data_as_of || "—"}
              {result.explainable_recommendation.writer
                ? ` · written by ${result.explainable_recommendation.writer}`
                : ""}
            </p>
          </div>
          <KpiRow
            forecast={result.demand_forecast.forecast_units}
            totalCost={result.total_cost}
            deliveryHours={result.delivery_time_hours}
            riskScore={result.risk_score}
            solver={result.optimization_status}
          />
          {result.explainable_recommendation.kpi_note && (
            <p className="hint">{result.explainable_recommendation.kpi_note}</p>
          )}

          <div className="grid">
            <section className="panel">
              <h2>Supplier allocation</h2>
              <table>
                <thead>
                  <tr>
                    <th>Supplier</th>
                    <th>Units</th>
                    <th>Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {result.supplier_allocation.map((row) => (
                    <tr key={row.supplier_code}>
                      <td>
                        {row.supplier_code} · {row.supplier_name}
                      </td>
                      <td>{row.units.toLocaleString()}</td>
                      <td>{money(row.cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.explainable_recommendation.allocation_note && (
                <p className="hint">{result.explainable_recommendation.allocation_note}</p>
              )}
            </section>
            <section className="panel">
              <h2>Routes</h2>
              <table>
                <thead>
                  <tr>
                    <th>Lane</th>
                    <th>Mode</th>
                    <th>Qty</th>
                  </tr>
                </thead>
                <tbody>
                  {result.routes.map((row) => (
                    <tr key={row.route_code + row.warehouse_code}>
                      <td>
                        {row.route_code} → {row.warehouse_code}
                      </td>
                      <td>{row.mode}</td>
                      <td>{row.quantity.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.explainable_recommendation.routes_note && (
                <p className="hint">{result.explainable_recommendation.routes_note}</p>
              )}
            </section>
          </div>

          <section className="panel">
            <h2>Inventory plan</h2>
            <p>
              Available {result.inventory_plan.total_available ?? "—"} · net buy{" "}
              {result.inventory_plan.net_requirement ?? "—"}
            </p>
            {result.explainable_recommendation.inventory_note && (
              <p className="hint">{result.explainable_recommendation.inventory_note}</p>
            )}
          </section>

          <HumanReviewPanel
            status={result.review_status}
            warning={result.llm_warning}
            constraints={result.human_constraints}
            busy={loading}
            onApprove={(note) => void run(() => reviewDecision(result.run_id, "approve", note))}
            onRevise={(feedback) => void run(() => reviewDecision(result.run_id, "revise", feedback))}
          />

          <section className="panel">
            <h2>What-if</h2>
            <div className="row wrap">
              <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
                <option value="demand_increase">Demand increase</option>
                <option value="supplier_failure">Supplier failure</option>
                <option value="price_increase">Price increase</option>
                <option value="fuel_increase">Fuel increase</option>
                <option value="route_disruption">Route disruption</option>
                <option value="inventory_shortage">Inventory shortage</option>
              </select>
              <input type="number" value={pct} onChange={(e) => setPct(Number(e.target.value))} title="Percent" />
              <input value={supplierCode} onChange={(e) => setSupplierCode(e.target.value)} title="Supplier code" />
              <button
                type="button"
                disabled={loading}
                onClick={() =>
                  void run(() =>
                    runWhatIf({
                      run_id: result.run_id,
                      scenario,
                      pct,
                      supplier_code: supplierCode,
                    })
                  )
                }
              >
                Re-run scenario
              </button>
            </div>
            <div className="row wrap">
              <input value={nlScenario} onChange={(e) => setNlScenario(e.target.value)} title="Natural language scenario" />
              <button
                type="button"
                disabled={loading}
                onClick={() =>
                  void run(() =>
                    runWhatIf({
                      run_id: result.run_id,
                      scenario: "natural_language",
                      text: nlScenario,
                    })
                  )
                }
              >
                Run natural-language scenario
              </button>
            </div>
            <ComparisonTable comparison={result.what_if?.comparison} />
            {result.what_if?.comparison?.unmet_demand && result.what_if.comparison.unmet_demand.scenario > 0 && (
              <p className="warning">
                <strong>Warning:</strong> Scenario results in {result.what_if.comparison.unmet_demand.scenario.toLocaleString()} units of unmet demand.
              </p>
            )}
          </section>

          {result.explainable_recommendation.reason && (
            <section className="panel">
              <h2>Explainable recommendation</h2>
              <pre className="reason">{result.explainable_recommendation.reason}</pre>
            </section>
          )}

          {result.retrieved_evidence && result.retrieved_evidence.length > 0 && (
            <section className="panel">
              <h2>Retrieved evidence</h2>
              <ul className="evidence">
                {result.retrieved_evidence.map((item, index) => (
                  <li key={index}>
                    <strong>{item.title}</strong>
                    {item.relevance && <p>{item.relevance}</p>}
                    <p>{item.snippet}</p>
                  </li>
                ))}
              </ul>
            </section>
          )}


        </>
      )}
    </div>
  );
}
