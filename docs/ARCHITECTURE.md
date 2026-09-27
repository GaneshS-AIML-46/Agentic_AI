# Architecture

SupplyChainAI turns a natural-language supply-chain request into an explainable plan.

```
User → React UI → FastAPI → LLM router (intent)
      → LangGraph supervisor
      → RAG (hybrid) + five specialist agents
      → OR-Tools MILP
      → Validator
      → What-if (optional)
      → Explainer
```

## Hard rule

The language model **parses intent** and **writes explanations**. It does **not** choose order quantities or total cost. Those come from OR-Tools using database facts.

## Agents

| Agent | Inputs | Outputs |
|---|---|---|
| Demand | `orders` history, user quantity | forecast + demand_to_meet |
| Supplier | `supplier_products`, `suppliers` | eligible offers |
| Route | `routes`, open `risk_events` | feasible lanes + effective cost |
| Inventory | `inventory`, warehouses | available, safety stock, net requirement |
| Risk | events, weather, fuel index, reliability | 0–100 score + drivers |

Shared state lives in `backend/app/graph/state.py`. Conditional **re-plan** relaxes lead time / low-risk hard constraints if the solver is infeasible (`MAX_REPLAN`).

## RAG

Markdown in `data/knowledge/` is chunked, embedded (Gemini or deterministic mock vectors), stored in `document_chunks.embedding` (pgvector) and `tsv` (PostgreSQL FTS). Retrieval = dense kNN + `ts_rank`, fused with Reciprocal Rank Fusion, then a lexical overlap rerank.

## Optimization

Variables `x[supplier, route]` = units. Constraints: demand (net requirement), supplier capacity, MOQ, route capacity, warehouse remaining space, optional low-risk concentration and reliability floor. Objective: procurement + transport×fuel + holding + reliability penalty.

## What-if

Scenarios patch **facts** (demand, prices, fuel, inventory factor, failed supplier, disrupted route) and re-run agents + solver. Comparison is baseline vs scenario on cost, time, risk, unmet demand.
