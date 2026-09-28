
# Product A briefing

# Product A

SKU PROD-A is a standard industrial fastener kit. Unit of measure is "unit".
Typical monthly demand in the synthetic history is about 8,500-11,000 units with a
Q4 seasonal lift.

Qualified sources and published offer facts live in supplier_products (price, monthly
capacity, lead time, MOQ). All seven demo suppliers can make Product A.

On-hand at the four DCs is intentionally thin versus a 10,000-unit next-month request,
so the plan should procure most of the volume rather than consume stock only.

Example decision request:
"I need 10,000 units of Product A next month. Find the lowest-cost supply plan with low risk."

Interpretation:
- product = Product A / PROD-A
- quantity = 10000 (user-specified; do not replace with forecast unless quantity omitted)
- horizon = next calendar month, lead_time_days <= 31
- objective = minimize cost subject to a low-risk reliability floor
