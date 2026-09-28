
# Risk scoring rubric

# Risk score (0-100)

Composite risk used by the Risk Agent is a weighted blend of:
- Supplier reliability: 40%  (score contribution = (1 - reliability_score) * 100)
- Open disruption severity: 30%  (high=80, medium=45, low=15, none=0)
- Route / weather disruption factor: 20%
- Concentration risk: 10%  (Herfindahl of allocated volume)

"Low risk" user language maps to:
- reliability_score >= 0.90 for the majority of volume
- no more than 15% of volume on suppliers with risk_tier = high
- avoid routes with status disrupted
- prefer not to place more than 50% of volume on a single supplier

The mathematical solver may add a risk penalty term
  penalty = RISK_PENALTY_WEIGHT * (1 - reliability) * unit_price * quantity
so that cheaper unreliable sources are not always selected. The penalty weight is a
configuration value, not an LLM-invented number.
