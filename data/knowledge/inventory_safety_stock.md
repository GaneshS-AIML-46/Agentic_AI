
# Inventory and safety-stock rules

# Safety stock and reorder policy

Safety stock for Product A is calibrated to cover 7-10 days of forecast demand across
the four DCs (Rotterdam, Chicago, Singapore, Mumbai). On-hand inventory is usable only
after subtracting reserved quantity.

Net procurement requirement:
  net = max(0, forecast_demand - (on_hand - reserved) + safety_stock_gap)

If on-hand already covers forecast plus safety stock, procurement may still be used to
rebalance between DCs, but the solver should not buy more than net + 5% unless a
supplier MOQ forces a bump.

Holding cost is charged on ending inventory at the warehouse holding_cost_per_unit.
Do not invent holding costs; use inventory.holding_cost_per_unit from the database.

Reorder point is an alert, not a hard solver constraint. The hard constraints are
warehouse capacity_units and supplier monthly_capacity.
