from __future__ import annotations

from app.agents.schemas import AgentBundle
from app.optimization.solver import SolverResult


def validate_plan(bundle: AgentBundle, solver: SolverResult) -> dict:
    issues: list[str] = []
    ok = True
    filled = sum(a.quantity for a in solver.allocations)
    if solver.status in {"OPTIMAL", "FEASIBLE"}:
        if filled + 1 < bundle.inventory.net_requirement:
            ok = False
            issues.append(
                f"Allocation {filled} below net requirement {bundle.inventory.net_requirement}"
            )
        by_sup: dict[str, int] = {}
        cap = {o.supplier_code: o.monthly_capacity for o in bundle.suppliers.offers}
        for a in solver.allocations:
            by_sup[a.supplier_code] = by_sup.get(a.supplier_code, 0) + a.quantity
        for code, qty in by_sup.items():
            if qty > cap.get(code, 0):
                ok = False
                issues.append(f"{code} allocated {qty} over capacity {cap.get(code)}")
        if not bundle.evidence:
            issues.append("No RAG evidence attached (non-blocking)")
    else:
        ok = False
        issues.append(solver.infeasibility or solver.status)

    return {
        "ok": ok,
        "issues": issues,
        "filled": filled,
        "net_requirement": bundle.inventory.net_requirement,
    }
