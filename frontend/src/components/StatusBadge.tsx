export default function StatusBadge({ status }: { status?: string | null }) {
  const label = status || "unknown";
  const tone =
    label === "approved" || label === "OPTIMAL" || label === "FEASIBLE"
      ? "ok"
      : label === "pending_review" || label === "revised"
        ? "wait"
        : "bad";
  return <span className={`status status-${tone}`}>{label.replace(/_/g, " ")}</span>;
}
