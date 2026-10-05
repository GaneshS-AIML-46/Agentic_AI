function money(n: number | null | undefined) {
  if (n == null) return "—";
  return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export default function KpiRow({
  forecast,
  totalCost,
  deliveryHours,
  riskScore,
  solver,
}: {
  forecast?: number;
  totalCost: number | null;
  deliveryHours: number | null;
  riskScore: number | null;
  solver: string | null;
}) {
  return (
    <section className="kpis">
      <div className="kpi">
        <span>Forecast</span>
        <strong>{forecast ?? "—"}</strong>
      </div>
      <div className="kpi">
        <span>Total cost</span>
        <strong>{money(totalCost)}</strong>
      </div>
      <div className="kpi">
        <span>Delivery (h)</span>
        <strong>{deliveryHours ?? "—"}</strong>
      </div>
      <div className="kpi">
        <span>Risk score</span>
        <strong>{riskScore ?? "—"}</strong>
      </div>
      <div className="kpi">
        <span>Solver</span>
        <strong>{solver || "—"}</strong>
      </div>
    </section>
  );
}
