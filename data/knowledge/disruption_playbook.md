# SYNTHETIC — SupplyChainAI demo knowledge base
# Disruption playbook

# Active disruption notes (aligned with synthetic risk_events)

1. Typhoon window, South China Sea / Hai Phong. Affects Apex Components (SUP-A) ocean
   exports, especially RT-A-ROT-OC. Mitigation: cap SUP-A share, prefer SUP-B / SUP-E
   for European demand and SUP-C / SUP-D for Asia DCs.

2. Rotterdam berth congestion. Adds 24-36 hours to inbound ocean. Does not block truck
   from Baltic Parts or EuroForge. Mitigation: EU-origin truck lanes remain preferred
   for WH-ROT.

3. Marine fuel index is above the 90-day baseline (see market_prices). Apply fuel
   surcharge via route.fuel_factor rather than ad-hoc percentages.

4. Gulf Manufacturing (SUP-G) had a closed quality CAPA. Status is monitor-only; it is
   not a current exclusion unless the user asks for very low risk, in which case keep
   SUP-G below 15% of volume.

If a supplier failure what-if is applied, remove that supplier's capacity entirely and
re-solve. Do not silently substitute invented capacity from other vendors.
