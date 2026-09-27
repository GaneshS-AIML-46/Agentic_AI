# Data dictionary (synthetic)

All tables are demo data. `is_synthetic=true` on source rows.

| Table | Purpose |
|---|---|
| products | SKUs including Product A (`PROD-A`) |
| suppliers | 7 vendors with reliability and risk tier |
| supplier_products | unit price, monthly capacity, lead time, MOQ |
| warehouses | 4 DCs (Rotterdam, Chicago, Singapore, Mumbai) |
| inventory | on-hand, reserved, reorder point, safety stock, holding cost |
| routes | supplier→warehouse lanes with mode, km, hours, cost, capacity, fuel factor |
| orders | 24 months of seasonal demand |
| shipments | sample historical inbound |
| risk_events | typhoon, port congestion, fuel spike, closed quality CAPA |
| market_prices | marine fuel and diesel indices |
| weather_events | typhoon / winter storm |
| documents / document_chunks | RAG corpus + embeddings + tsvector |
| decision_runs | persisted plans and what-if children |
