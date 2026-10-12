# Graph model

Nodes represent economic components. Relationships retain directed endpoints,
mechanism, expected lag, explicit evidence state, confidence, alternative
explanations, review status, and evidence links.

The illustrative chain is:

AI Capex → HBM Demand → Memory Capacity Allocation → Consumer Memory Prices →
Device Prices → Consumer Demand.

Synthetic evidence only illustrates this chain; it cannot causally support it.
Direction describes a mechanism in context, not whether a metric is good or bad.
Confidence is an epistemic judgment, not a transmission elasticity.

Initially relational storage and API traversal suffice. Evaluate a dedicated graph
database only when measured traversal needs justify operational cost.
