# SYNTHETIC — SupplyChainAI demo knowledge base
# Fuel surcharge policy

# Fuel surcharge

Transport cost used by the optimizer is:
  transport = quantity * cost_per_unit * fuel_factor * fuel_scenario_multiplier

fuel_scenario_multiplier defaults to 1.0. A "fuel increase 15%" what-if sets it to 1.15.

Procurement unit_price is not a function of fuel. Do not inflate supplier prices when
the user asks about fuel.

Marine fuel index and diesel_index observations are stored in market_prices. They are
evidence for the Risk Agent and explanations, not a second cost formula. The solver
must use the route table, not a newly estimated bunker formula.
