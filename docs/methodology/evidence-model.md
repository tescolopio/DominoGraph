# Evidence model

Evidence and relationships use explicit states:

`observed`, `inferred`, `correlated`, `causally_supported`, `forecast`, `advocated`,
`policy_proposed`, `policy_adopted`, `implemented`, `documented_coordination`,
`unverified`, `disputed`.

These are semantic categories, not an ordered ladder of certainty. An observed
price is not a forecast; advocacy is not implemented policy; correlation is not
causation. A policy announcement and subsequent economic outcome are separate
records. Documented coordination requires direct documentation, not similarity
between a forecast and an outcome.

Link evidence to source records and exact content or observation references.
Store counter-evidence alongside support. Empty contradiction lists are explicit
search gaps. Confidence does not replace evidence or measure causal effect size.

Provenance includes source URL, retrieval/publication/observation dates, vintage,
collector and transformation versions, validation state, and raw snapshot lineage.
Revisions must be appended, never silently overwritten. Replaying an assessment
must use its retained observation IDs and versioned rules, not today's latest data.

Raw content hashes establish content identity, not authenticity or truth. Review
licensing and methodological validity independently of technical validation.

The provenance endpoint follows only retained forward references. It does not
expand a node into all current metrics, observations, assessments or neighboring
relationships. Use node detail and graph endpoints for that contextual exploration.
Adding later vintages therefore cannot alter an existing assessment's lineage.

Both relationships and hypotheses require approval plus supporting evidence of
the matching type before using `causally_supported` or `documented_coordination`.
Approval alone cannot promote synthetic evidence into those classifications.
