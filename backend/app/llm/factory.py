from __future__ import annotations

import json
import re
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.core.config import settings


class Intent(BaseModel):
    product_query: str = "Product A"
    quantity: int | None = None
    horizon: str = "next_month"
    lead_time_days_max: int = 31
    objective: str = "min_cost_low_risk"
    low_risk: bool = True
    notes: str = ""


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
        return Intent.model_validate(data).model_dump()


def get_llm() -> LLMClient:
    provider = settings.effective_llm_provider
    if provider == "gemini" and settings.resolved_gemini_key:
        return GeminiLLM()
    return MockLLM()


def parse_intent(query: str) -> Intent:
    llm = get_llm()
    system = (
        "You extract supply-chain planning intent. "
        "quantity is an integer or null if not stated. "
        "objective is one of min_cost, min_cost_low_risk, min_time, balanced. "
        "low_risk is true if the user wants low risk. "
        "Do not invent demand numbers that were not requested."
    )
    try:
        data = llm.complete_json(system, query)
        return Intent.model_validate(data)
    except Exception:
        return Intent.model_validate(MockLLM().complete_json(system, query))
