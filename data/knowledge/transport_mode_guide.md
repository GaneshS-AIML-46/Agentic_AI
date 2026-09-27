# SYNTHETIC — SupplyChainAI demo knowledge base
# Transport mode guide

# Mode selection

Ocean: lowest cost per unit on Asia-Europe and Asia-US lanes; transit 5-22 days.
Truck: used inside EU and North America; sensitive to diesel_index.
Air: only for short lead-time gaps or infeasible ocean/truck lead times. Air cost_per_unit
is several times ocean; the solver should use air only when lead_time_days of ocean
options exceed the planning horizon.

Fuel factor on each route multiplies transport cost. If a what-if scenario increases fuel,
apply the percentage to cost_per_unit * fuel_factor, not to procurement price.

Disrupted routes (status != open) are infeasible. Port congestion at Rotterdam adds
delay but does not zero capacity unless the risk event severity is high and the route
is named in risk_events.affected_route_id.

Do not compute "best route" as a language-model guess. Rank feasible routes using
database cost_per_unit, transit_hours, capacity_units, and open disruption flags.
