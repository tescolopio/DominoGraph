# Contributing

Challenge assumptions and seek counter-evidence. Prefer a small reproducible
change to an opaque conclusion. Do not present synthetic examples as market data.

## Development

Follow the README setup and run `python -m unittest discover -s tests -v`.
Submit tests for validation, revision handling, foreign-key integrity, provenance,
scoring boundaries, and methodological assumptions affected by your change.
Generate schemas from the canonical models rather than maintaining conflicting
definitions. Never change published historical records in place.

## Review requirements

A causal relationship proposal must include:

- Mechanism and expected lag.
- Supporting evidence and counter-evidence (explicitly identify search gaps).
- Confidence, uncertainty, and alternative explanations.
- Source-linked methodology and falsifiable predictions.
- Human review before promotion to an approved causal finding.

A source proposal must document publisher, methodology, update cadence, revision
policy, license/redistribution permissions, and limitations. Source tier indicates
verification effort, not truth. Paid or restricted data must not enter this repo.

Scoring changes must document units, contextual direction, baselines, weights,
missing-data handling, version, and reproducible examples. Ontology changes,
high-impact scores, major hypotheses, and causal claims require maintainer review.
AI output must include provider/model version and input/evidence lineage; provider
choice must never be encoded in canonical objects.

Before publishing, inspect the diff and scan for secrets. Do not commit `.env`,
raw restricted documents, personal financial information, or private user data.
Report security concerns privately as described in SECURITY.md.
