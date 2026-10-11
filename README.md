# DominoGraph
Open-source economic intelligence platform that maps global financial, policy, market, and real-economy dependencies into a traceable graph of risks, supports, firebreaks, hypotheses, and transmission paths.

## Runnable first milestone

The Memory & Compute pilot provides a source registry, immutable observations,
versioned scoring, explicit evidence and counter-evidence, hypotheses, dependency
inspection, and an illustrative scenario runner.

**All included economic data is synthetic.** It demonstrates the plumbing, not
the state of markets, institutional intent, documented coordination, or predictive
accuracy. Do not use the sample assessments to make financial decisions.

### Quick start

Requires Python 3.11 or newer. From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m scripts.seed
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000> for the dashboard and `/docs` for the API.
Seeding is explicit; importing the API must not invent data.
SQLite is the default local metadata store. Set `DATABASE_URL` for PostgreSQL.
`.env.example` describes configuration; commands do not automatically load `.env`.
For PostgreSQL, install `python -m pip install -e '.[postgres]'` and set a
`postgresql+psycopg://` connection URL using locally managed credentials.

```sh
python -m unittest discover -s tests -v
python -m scripts.export --help
```

### Docker

```sh
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml run --rm api python -m scripts.seed
docker compose -f docker/docker-compose.yml up
```

The named volume retains local observations between restarts. The port is bound
to loopback; Docker does not make the pilot safe for public multi-tenant deployment.

The dashboard intentionally uses browser-native HTML/CSS/JavaScript: no vendor AI
dependency, frontend build pipeline, or dedicated graph database is necessary to
prove the pilot. See [the roadmap](ROADMAP.md) for React, analytical Parquet storage,
production scheduling, and live-source integrations.

## Inspect, rather than trust

Select a domino to see Pressure, Firebreak, Support, Dependency, Transmission,
and Confidence independently. Inspect metric vintages, upstream/downstream
mechanisms, intervention records, hypotheses, and counter-evidence. Trace buttons
resolve:

```text
Assessment → Node / Metric / Relationship → Observation / Evidence → Source
```

Relationships have mechanisms and explicit evidence states. Confidence is not a
causal coefficient. Scenarios are conditional illustrations, not forecasts.
Institutional statements remain separate from observed economic outcomes.
Unreviewed model outputs are proposals, not published causal findings.

## Project guide

- [Architecture](docs/architecture/overview.md) and [canonical model](docs/architecture/data-model.md)
- [Evidence](docs/methodology/evidence-model.md), [scoring](docs/methodology/scoring.md), and [scenarios](docs/methodology/scenario-modeling.md)
- [Contribution guide](CONTRIBUTING.md), [security](SECURITY.md), and [code of conduct](CODE_OF_CONDUCT.md)
- [Roadmap and initial issue backlog](ROADMAP.md) and [changelog](CHANGELOG.md)

Software is MIT licensed. Data licensing is independent: only synthetic examples
are distributed here. A public API or accessible document does not automatically
grant redistribution rights.
