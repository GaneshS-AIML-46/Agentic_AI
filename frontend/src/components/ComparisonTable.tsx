export default function ComparisonTable({
  comparison,
}: {
  comparison?: Record<string, { baseline: number; scenario: number; delta: number }>;
}) {
  if (!comparison) return null;
  return (
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
        {Object.entries(comparison).map(([key, value]) => {
          const labels: Record<string, string> = {
            total_cost: "Total Cost",
            delivery_time_hours: "Delivery Hours",
            risk_score: "Risk Score",
            unmet_demand: "Unmet Demand",
          };
          const label = labels[key] || key;
          return (
            <tr key={key}>
              <td>{label}</td>
              <td>{value.baseline.toLocaleString(undefined, { maximumFractionDigits: 1 })}</td>
              <td>{value.scenario.toLocaleString(undefined, { maximumFractionDigits: 1 })}</td>
              <td>{value.delta > 0 ? `+${value.delta.toLocaleString(undefined, { maximumFractionDigits: 1 })}` : value.delta.toLocaleString(undefined, { maximumFractionDigits: 1 })}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
