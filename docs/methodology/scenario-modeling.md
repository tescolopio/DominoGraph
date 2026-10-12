# Scenario modeling

Scenarios answer conditional “what if” questions, not “what will happen.”
Retain the initial node/shock, horizon, assumptions, relationship/evidence IDs,
parameters, methodology version, and limitations.

Never use epistemic confidence as a propagation coefficient. A coefficient must
be separately documented with units and justification. Synthetic pilot coefficients
are invented demonstration assumptions, not estimated elasticities.

Bound inputs and traversal. Explain skipped links, horizon/lag behavior, and cycle
handling. Do not silently count repeated paths as independent evidence.
Independent-path, linear, or single-pass propagation is a modeling assumption and
must be identified in outputs. Scenarios do not authorize causal promotion of edges.

Before empirical use, validate coefficients, lags, feedback, nonlinearities, and
uncertainty against historical out-of-sample events and alternative mechanisms.

`bounded-path-v2` sums all accepted path contributions for each target using
accurate floating-point summation, then clamps the final result to [-100, 100].
Clamping after each contribution made mixed-sign results depend on relationship
ordering. The new version is included in scenario identity; retained v1 scenarios
remain readable without recalculation. New runs use only current relationship
versions and exclude rejected or needs-revision versions.
