import { FormEvent, useState } from "react";
import StatusBadge from "./StatusBadge";

export default function HumanReviewPanel({
  status,
  warning,
  constraints,
  busy,
  onApprove,
  onRevise,
}: {
  status?: string | null;
  warning?: string | null;
  constraints?: { kind: string; code?: string | null; value?: number | null; raw?: string }[];
  busy: boolean;
  onApprove: (note: string) => void;
  onRevise: (feedback: string) => void;
}) {
  const [feedback, setFeedback] = useState("exclude supplier SUP-C and max lead time 25 days");

  function submit(event: FormEvent) {
    event.preventDefault();
    onRevise(feedback);
  }

  return (
    <section className="panel">
      <div className="row">
        <h2>Human review</h2>
        <StatusBadge status={status || "pending_review"} />
      </div>
      <p className="hint">
        Approve the plan, or send a constraint such as “exclude supplier SUP-C” or “fuel +15%”.
      </p>
      {warning && <p className="error">{warning}</p>}
      {!!constraints?.length && (
        <ul className="evidence">
          {constraints.map((item, index) => (
            <li key={`${item.kind}-${index}`}>
              <strong>{item.kind}</strong>
              <p>{item.raw || [item.code, item.value].filter((part) => part != null).join(" ")}</p>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={submit}>
        <label htmlFor="feedback">Planner feedback</label>
        <textarea id="feedback" rows={3} value={feedback} onChange={(e) => setFeedback(e.target.value)} />
        <div className="row wrap">
          <button type="button" onClick={() => onApprove(feedback)} disabled={busy}>
            Approve plan
          </button>
          <button type="submit" disabled={busy}>
            Apply feedback and replan
          </button>
        </div>
      </form>
    </section>
  );
}
