from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.core.config import settings
from app.hitl.constraints import HumanConstraint, parse_human_text

logger = logging.getLogger(__name__)


class Intent(BaseModel):
    product_query: str = "Product A"
    quantity: int | None = None
    horizon: str = "next_month"
    lead_time_days_max: int | None = 31
    objective: str = "min_cost_low_risk"
    low_risk: bool = True
    notes: str | None = ""
    failed_supplier_codes: list[str] = Field(default_factory=list)
    disrupted_route_codes: list[str] = Field(default_factory=list)
    constraints: list[HumanConstraint] = Field(default_factory=list)
    llm_provider: str = "mock"
    llm_warning: str | None = None

    @property
    def safe_lead_time(self) -> int:
        return self.lead_time_days_max if self.lead_time_days_max is not None else 31

    @property
    def safe_notes(self) -> str:
        return self.notes if self.notes is not None else ""


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str) -> dict[str, Any]: ...


class MockLLM:
    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        qty = None
        m = re.search(r"(\d{1,3}(?:,\d{3})+|\d+)\s*units", user, re.I)
        if m:
            qty = int(m.group(1).replace(",", ""))
        product = "Product A"
        pm = re.search(r"product\s+([A-Ja-j])\b", user, re.I)
        if pm:
            product = f"Product {pm.group(1).upper()}"
        else:
            nm = re.search(r"\b(PROD-[A-J])\b", user, re.I)
            if nm:
                product = nm.group(1).upper()
        low_risk = "low risk" in user.lower() or "low-risk" in user.lower()
        objective = "min_cost_low_risk" if low_risk else "min_cost"
        if "fast" in user.lower() or "lead time" in user.lower():
            objective = "min_time"
        return Intent(
            product_query=product,
            quantity=qty,
            horizon="next_month" if "month" in user.lower() else "unspecified",
            lead_time_days_max=31,
            objective=objective,
            low_risk=low_risk or "risk" in user.lower(),
            notes="Parsed by mock LLM (regex). Set GEMINI_API_KEY for Gemini.",
            llm_provider="mock",
        ).model_dump()


class GeminiLLM:
    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        from google import genai

        client = genai.Client(api_key=settings.resolved_gemini_key)
        prompt = (
            f"{system}\n\nUser request:\n{user}\n\n"
            "Return ONLY JSON with keys: product_query, quantity, horizon, "
            "lead_time_days_max, objective, low_risk, notes."
        )
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        text = response.text or "{}"
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).rstrip("`").strip()
        data = json.loads(text)
        parsed = Intent.model_validate(data)
        parsed.llm_provider = "gemini"
        return parsed.model_dump()


def _parse_json_text(text: str) -> dict[str, Any]:
    raw = (text or "{}").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).rstrip("`").strip()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Gemini response was not a JSON object")
    return data


_gemini_slot = 1  # Start from key 2 (index 1) since key 1 may be quota-limited


def _gemini_models() -> list[str]:
    return [settings.gemini_model]


def _gemini_once(api_key: str, model: str, system: str, user: str) -> dict[str, Any]:
    import time
    from google import genai

    client = genai.Client(api_key=api_key)
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=f"{system}\n\n{user}",
            )
            return _parse_json_text(response.text or "{}")
        except Exception as exc:
            last_exc = exc
            err_str = str(exc)
            # Only retry on transient server errors (5xx), not on quota or not-found
            if "500" in err_str or "503" in err_str or "ServerError" in type(exc).__name__:
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    "Gemini model %s transient error (attempt %s/3), retrying in %ss: %s",
                    model, attempt + 1, wait, type(exc).__name__
                )
                time.sleep(wait)
                continue
            raise
    assert last_exc is not None
    raise last_exc


def gemini_json(system: str, user: str) -> dict[str, Any]:
    """Rotate Gemini keys, retrying transient errors. Skips quota-exhausted keys."""
    global _gemini_slot
    keys = settings.gemini_keys
    if not keys:
        raise RuntimeError("No Gemini API key is configured")
    start = _gemini_slot % len(keys)
    errors: list[str] = []
    for offset in range(len(keys)):
        index = (start + offset) % len(keys)
        for model in _gemini_models():
            try:
                data = _gemini_once(keys[index], model, system, user)
                _gemini_slot = (index + 1) % len(keys)
                data["_gemini_slot"] = index + 1
                data["_gemini_model"] = model
                return data
            except Exception as exc:
                logger.warning("Gemini key %s model %s failed (%s)", index + 1, model, type(exc).__name__)
                errors.append(f"key {index + 1} {model}: {type(exc).__name__}")
    raise RuntimeError("; ".join(errors))


def provider_order(task: str, available: set[str]) -> list[str]:
    """Intent uses the fastest key first. Written sections use OpenAI first. Gemini is the spare."""
    preferred = ("groq", "openai", "gemini") if task == "intent" else ("openai", "groq", "gemini")
    return [name for name in preferred if name in available]


def available_providers() -> list[str]:
    present: set[str] = set()
    if settings.groq_api_key:
        present.add("groq")
    if settings.openai_api_key:
        present.add("openai")
    if settings.resolved_gemini_key:
        present.add("gemini")
    return [name for name in ("groq", "openai", "gemini") if name in present]


def _providers_for(task: str) -> list[str]:
    """Prefer the configured provider, then try configured alternatives on failure."""
    available = set(available_providers())
    if not available:
        return []
    configured = settings.effective_llm_provider.strip().lower()
    preferred = [configured] if configured in available else []
    preferred.extend(provider_order(task, available))
    return list(dict.fromkeys(preferred))


def _openai_compatible_json(base_url: str, api_key: str, model: str, system: str, user: str) -> dict[str, Any]:
    import httpx

    response = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        },
        timeout=45,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return _parse_json_text(content)


def complete_json(provider: str, system: str, user: str) -> dict[str, Any]:
    if provider == "gemini":
        return gemini_json(system, user)
    if provider == "openai":
        return _openai_compatible_json(
            "https://api.openai.com/v1",
            settings.openai_api_key,
            settings.openai_model,
            system,
            user,
        )
    if provider == "groq":
        models = [settings.groq_model, "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
        last_error: Exception | None = None
        seen: set[str] = set()
        for model in models:
            if not model or model in seen:
                continue
            seen.add(model)
            try:
                return _openai_compatible_json(
                    "https://api.groq.com/openai/v1",
                    settings.groq_api_key,
                    model,
                    system,
                    user,
                )
            except Exception as exc:
                last_error = exc
                message = str(exc)
                if "404" not in message and "503" not in message and "429" not in message:
                    raise
        assert last_error is not None
        raise last_error
    raise RuntimeError(f"Unknown provider {provider}")


def fallback_narrative(
    query: str,
    facts: dict[str, Any],
    evidence: list[dict[str, Any]],
    trace: list[str],
) -> dict[str, Any]:
    """Query-specific text used when Gemini is unavailable. Numbers stay the solver's."""
    reason = (
        f"For this request — {query} — meet {facts.get('demand_to_meet')} units of "
        f"{facts.get('product_name')} (forecast {facts.get('forecast_units')}). "
        f"Net buy is {facts.get('net_requirement')} units. "
        f"OR-Tools status {facts.get('status')} at total cost {facts.get('total_cost')} "
        f"(procurement {facts.get('procurement_cost')} + transport {facts.get('transport_cost')}). "
        f"Delivery {facts.get('delivery_time_hours')} hours. Risk score {facts.get('risk_score')}. "
        "Quantities come from the OR-Tools solver, not from the language model."
    )
    notes = []
    for item in evidence:
        title = item.get("title") or "Document"
        snippet = (item.get("snippet") or "")[:180]
        notes.append(
            {
                "title": title,
                "relevance": f"For \"{query}\", {title} applies because it says: {snippet}",
            }
        )
    steps = [f"Read the request: {query}"] + [f"Step: {line}" for line in trace]
    steps.append("OR-Tools calculated quantities and cost from the facts above.")
    return {"summary": reason[:280], "reason": reason, "evidence": notes, "trace": steps}


def _gemini_failure(query: str, evidence: list[dict[str, Any]], exc: Exception) -> dict[str, Any]:
    return {
        "summary": "Explanation not available.",
        "reason": "",
        "kpi_note": "",
        "allocation_note": "",
        "routes_note": "",
        "inventory_note": "",
        "evidence": [],
        "trace": ["Explanation generation skipped due to API failure."],
        "gemini_error": str(exc),
    }


def narrate_plan(
    query: str,
    facts: dict[str, Any],
    evidence: list[dict[str, Any]],
    trace: list[str],
) -> dict[str, Any]:
    writers = _providers_for("narrative")
    if not writers:
        return _gemini_failure(query, evidence, RuntimeError("No LLM API key is configured"))
    system = (
        "You are a supply-chain planner. Write a concise explanation of a supply plan for the given request. "
        "Use ONLY the numbers and codes from FACTS. Do not invent quantities, costs, suppliers, or routes. "
        "State that OR-Tools calculated the quantities. "
        "Return ONLY valid JSON with these exact keys: "
        "summary (1 sentence), reason (2-3 sentences), kpi_note (1 sentence), "
        "allocation_note (1 sentence), routes_note (1 sentence), inventory_note (1 sentence), "
        "evidence (list of {title, relevance}), trace (list of short step strings)."
    )
    # Slim payload: trim trace to last 6 steps and evidence snippets to 200 chars to avoid server 500s
    trimmed_trace = trace[-6:] if len(trace) > 6 else trace
    user = json.dumps(
        {
            "request": query,
            "facts": {
                k: v for k, v in facts.items()
                if k in (
                    "product_name", "forecast_units", "demand_to_meet", "net_requirement",
                    "status", "total_cost", "procurement_cost", "transport_cost",
                    "delivery_time_hours", "risk_score", "suppliers", "routes", "request",
                )
            },
            "evidence": [
                {"title": item.get("title"), "snippet": (item.get("snippet") or "")[:200]}
                for item in evidence[:4]
            ],
            "trace": trimmed_trace,
        },
        default=str,
    )
    errors: list[str] = []
    data: dict[str, Any] | None = None
    writer = ""
    for provider in writers:
        try:
            data = complete_json(provider, system, user)
            writer = provider
            break
        except Exception as exc:
            logger.warning("Narrative provider %s failed (%s): %s", provider, type(exc).__name__, exc)
            errors.append(f"{provider}: {exc}")
    if data is None:
        return _gemini_failure(query, evidence, RuntimeError("; ".join(errors)))

    def text_field(name: str) -> str:
        value = data.get(name)
        return value.strip() if isinstance(value, str) else ""

    reason = text_field("reason")
    if reason and "or-tools" not in reason.lower() and "solver" not in reason.lower():
        reason += "\nQuantities come from the OR-Tools solver, not from the language model."
    by_title = {
        str(item.get("title") or ""): str(item.get("relevance") or "").strip()
        for item in data.get("evidence") or []
        if isinstance(item, dict)
    }
    rewritten = []
    for item in evidence:
        title = item.get("title") or "Document"
        relevance = by_title.get(title) or ""
        if not relevance:
            relevance = f"{writer} did not explain {title} for this request."
        rewritten.append({"title": title, "relevance": relevance})
    written_trace = [str(step).strip() for step in data.get("trace") or [] if str(step).strip()]
    active_model = data.get("_gemini_model")
    if not active_model:
        active_model = {
            "openai": settings.openai_model,
            "groq": settings.groq_model,
        }.get(writer, "configured model")
    key_slot = data.get("_gemini_slot")
    writer_label = f"gemini key {key_slot} ({active_model})" if writer == "gemini" else f"{writer} ({active_model})"
    return {
        "summary": text_field("summary") or reason,
        "reason": reason or text_field("summary"),
        "kpi_note": text_field("kpi_note"),
        "allocation_note": text_field("allocation_note"),
        "routes_note": text_field("routes_note"),
        "inventory_note": text_field("inventory_note"),
        "evidence": rewritten,
        "trace": written_trace or [reason or f"{writer} returned no trace."],
        "writer": writer_label,
    }


def get_llm() -> LLMClient:
    provider = settings.effective_llm_provider
    if provider == "gemini" and settings.resolved_gemini_key:
        return GeminiLLM()
    return MockLLM()


def enrich_intent(intent: Intent, query: str) -> Intent:
    """Attach natural-language scenario constraints even when the LLM omits them."""
    constraints = parse_human_text(query)
    if not intent.constraints:
        intent.constraints = constraints
    else:
        known = {(c.kind, c.code, c.value) for c in intent.constraints}
        for item in constraints:
            key = (item.kind, item.code, item.value)
            if key not in known:
                intent.constraints.append(item)
    intent.failed_supplier_codes = list(
        dict.fromkeys(
            intent.failed_supplier_codes
            + [c.code for c in intent.constraints if c.kind == "exclude_supplier" and c.code]
        )
    )
    intent.disrupted_route_codes = list(
        dict.fromkeys(
            intent.disrupted_route_codes
            + [c.code for c in intent.constraints if c.kind == "exclude_route" and c.code]
        )
    )
    for item in intent.constraints:
        if item.kind == "max_lead_time_days" and item.value is not None:
            intent.lead_time_days_max = min(intent.safe_lead_time, int(item.value))
    return intent


def _coerce_intent_data(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize Gemini JSON response: replace None/invalid values with safe defaults."""
    if data.get("lead_time_days_max") is None:
        data["lead_time_days_max"] = 31
    if data.get("notes") is None:
        data["notes"] = ""
    if data.get("product_query") is None:
        data["product_query"] = "Product A"
    if data.get("horizon") is None:
        data["horizon"] = "next_month"
    if data.get("objective") is None:
        data["objective"] = "min_cost_low_risk"
    if data.get("low_risk") is None:
        data["low_risk"] = False
    return data


def parse_intent(query: str) -> Intent:
    system = (
        "You extract supply-chain planning intent from the user request. "
        "Return ONLY a JSON object with these exact keys: "
        "product_query (string), quantity (integer or null), horizon (string like 'next_month'), "
        "lead_time_days_max (integer, default 31), objective (one of: min_cost, min_cost_low_risk, min_time, balanced), "
        "low_risk (boolean), notes (string). "
        "Never return null for lead_time_days_max or notes — use default values instead. "
        "Do not invent demand numbers that were not explicitly requested."
    )
    providers = _providers_for("intent")
    if not providers:
        fallback = Intent.model_validate(MockLLM().complete_json(system, query))
        fallback.llm_warning = "No LLM API key is configured."
        return enrich_intent(fallback, query)
    errors: list[str] = []
    for provider in providers:
        try:
            data = complete_json(provider, system, query)
            data.pop("_gemini_slot", None)
            data.pop("_gemini_model", None)
            intent = Intent.model_validate(_coerce_intent_data(data))
            intent.llm_provider = provider
            return enrich_intent(intent, query)
        except Exception as exc:
            logger.warning("Intent provider %s failed (%s): %s", provider, type(exc).__name__, exc)
            errors.append(f"{provider}: {type(exc).__name__}")
    fallback = Intent.model_validate(MockLLM().complete_json(system, query))
    fallback.llm_provider = "mock"
    fallback.notes = fallback.safe_notes
    return enrich_intent(fallback, query)
