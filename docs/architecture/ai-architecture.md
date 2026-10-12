# Provider-neutral AI

Reasoning, research/extraction, and reviewer interfaces are replaceable contracts.
Adapters may later support hosted or local models. Canonical entities never require
a provider SDK or hard-coded model name.

Logical roles include a Reasoning Council, Domain Analyst, Research Agent, Evidence
Extractor, Adversarial Reviewer, Scenario Analyst, and Human Reviewer.

Use AI for judgment: causal proposals, evidence interpretation, counter-evidence
search, hypotheses, and methodology critique. Preserve input/source references,
provider/model version, uncertainty, and human disposition for published outputs.

Use deterministic code for ingestion, CSV parsing, normalization, validation,
calculations, and monitoring. An AI-generated relationship is a proposal; it must
acquire evidence and human review before promotion. No remote model runs are
required or performed by the synthetic pilot.
