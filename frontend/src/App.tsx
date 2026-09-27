import { FormEvent, useEffect, useState } from "react";
import { createDecision, DecisionResponse, fetchCatalog, runWhatIf } from "./api/client";

const EXAMPLE =
  "I need 10,000 units of Product A next month. Find the lowest-cost supply plan with low risk.";

function money(n: number | null | undefined) {
  if (n == null) return "—";
  return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export default function App() {
  const [query, setQuery] = useState(EXAMPLE);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DecisionResponse | null>(null);
  const [catalog, setCatalog] = useState<string>("");
  const [scenario, setScenario] = useState("supplier_failure");
  const [pct, setPct] = useState(20);
  const [supplierCode, setSupplierCode] = useState("SUP-C");

  useEffect(() => {
    fetchCatalog()
      .then((c) => {
        const products = (c.products || []).map((p: { sku: string }) => p.sku).join(", ");
        setCatalog(products);
      })
      .catch(() => setCatalog("API not reachable yet"));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      setResult(await createDecision(query));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function onWhatIf() {
    if (!result) return;
    setLoading(true);
    setError(null);
    try {
      setResult(
        await runWhatIf({
          run_id: result.run_id,
          scenario,
          pct,
          supplier_code: supplierCode,
        })
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <header>
        <div>
          <p className="eyebrow">Multi-agent decision intelligence</p>
          <h1>SupplyChainAI</h1>
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

      {error && <div className="error">{error}</div>}

      {result && (
        <>
          <section className="kpis">
            <Kpi label="Forecast" value={String(result.demand_forecast.forecast_units ?? "—")} />
            <Kpi label="Total cost" value={money(result.total_cost)} />
            <Kpi label="Delivery (h)" value={String(result.delivery_time_hours ?? "—")} />
            <Kpi label="Risk score" value={String(result.risk_score ?? "—")} />
            <Kpi label="Solver" value={result.optimization_status || "—"} />
          </section>

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
                  {result.supplier_allocation.map((s) => (
                    <tr key={s.supplier_code}>
                      <td>
                        {s.supplier_code} · {s.supplier_name}
                      </td>
                      <td>{s.units.toLocaleString()}</td>
                      <td>{money(s.cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
                  {result.routes.map((r) => (
                    <tr key={r.route_code + r.warehouse_code}>
                      <td>
                        {r.route_code} → {r.warehouse_code}
                      </td>
                      <td>{r.mode}</td>
                      <td>{r.quantity.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>

          <section className="panel">
            <h2>Inventory plan</h2>
            <p>
              Available {result.inventory_plan.total_available ?? "—"} · net buy{" "}
              {result.inventory_plan.net_requirement ?? "—"}
            </p>
            <table>
              <thead>
                <tr>
                  <th>DC</th>
                  <th>On hand</th>
                  <th>Reserved</th>
                  <th>Available</th>
                  <th>Safety</th>
                </tr>
              </thead>
              <tbody>
                {(result.inventory_plan.rows || []).map((r) => (
                  <tr key={r.warehouse_code}>
                    <td>{r.warehouse_code}</td>
                    <td>{r.on_hand}</td>
                    <td>{r.reserved}</td>
                    <td>{r.available}</td>
                    <td>{r.safety_stock}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

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
              <input
                type="number"
                value={pct}
                onChange={(e) => setPct(Number(e.target.value))}
                title="Percent"
              />
              <input
                value={supplierCode}
                onChange={(e) => setSupplierCode(e.target.value)}
                title="Supplier code"
              />
              <button type="button" onClick={onWhatIf} disabled={loading}>
                Re-run scenario
              </button>
            </div>
            {result.what_if?.comparison && (
              <table>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Baseline</th>
                    <th>Scenario</th>
                    <th>Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(result.what_if.comparison).map(([k, v]) => (
                    <tr key={k}>
                      <td>{k}</td>
                      <td>{v.baseline}</td>
                      <td>{v.scenario}</td>
                      <td>{v.delta}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="panel">
            <h2>Explainable recommendation</h2>
            <pre className="reason">{result.explainable_recommendation.reason}</pre>
          </section>

          <section className="panel">
            <h2>Retrieved evidence</h2>
            <ul className="evidence">
              {result.retrieved_evidence.map((e, i) => (
                <li key={i}>
                  <strong>{e.title}</strong>
                  <p>{e.snippet}</p>
                </li>
              ))}
            </ul>
          </section>

          <section className="panel">
            <h2>Agent trace</h2>
            <ol>
              {result.agent_trace.map((t, i) => (
                <li key={i}>{t}</li>
              ))}
            </ol>
            {result.validation?.issues?.length ? (
              <p className="hint">Validation: {result.validation.issues.join("; ")}</p>
            ) : null}
          </section>
        </>
      )}
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="kpi">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
