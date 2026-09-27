# SYNTHETIC — SupplyChainAI demo knowledge base
# Supplier sourcing policy (not a real corporate policy)

# Multi-source policy for critical SKUs

Critical SKUs such as Product A must not rely on a single supplier for more than 60% of
monthly volume when two or more qualified sources exist. Dual-source is required whenever
combined capacity of the top two suppliers is below 1.4x forecast demand.

Preferred allocation order when the objective is lowest cost with low risk:
1. Exclude suppliers with open high-severity events that affect more than 20% of their
   outbound capacity.
2. Prefer reliability_score >= 0.90 for at least 70% of allocated volume.
3. Honor supplier monthly_capacity and MOQ from the supplier_products table. Do not
   override those facts with estimated numbers.
4. Lead time must fit the requested horizon. "Next month" means lead_time_days <= 31
   unless air freight is explicitly allowed.

Vietnam-origin ocean lanes (Apex Components / SUP-A) carry elevated weather variance
during typhoon season. Treat those lanes as medium-high transit risk even when unit
price is attractive.

EuroForge (SUP-E) and Baltic Parts (SUP-B) are designated low-risk European sources.
They are appropriate when the user asks for "low risk" even if unit price is higher.
