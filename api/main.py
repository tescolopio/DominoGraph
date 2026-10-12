from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from core.scenarios import ScenarioLimitError, run_scenario
from core.store import Store
from schemas.models import Id, MODELS, Scenario

ROOT = Path(__file__).resolve().parents[1]


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    node_id: Id
    shock: Annotated[float, Field(ge=-100, le=100)]
    horizon_months: Annotated[int, Field(ge=1, le=120, strict=True)]


def create_app(store: Store | None = None):
    @asynccontextmanager
    async def lifespan(app):
        owned = store is None
        app.state.store = store or Store()
        app.state.store.initialize()
        yield
        if owned:
            app.state.store.engine.dispose()

    app = FastAPI(title="DominoGraph SYNTHETIC pilot", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(KeyError)
    async def missing_reference(request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc.args[0])})

    @app.get("/health")
    def health():
        app.state.store.all("node")
        return {"status": "ok", "schema_version": "1.0.0", "seeded": bool(app.state.store.all("node"))}

    @app.get("/api/nodes")
    def nodes():
        return app.state.store.all("node")

    @app.get("/api/nodes/{node_id}")
    def node_detail(node_id: str):
        database = app.state.store
        node = database.get("node", node_id)
        metrics = [m for m in database.all("metric") if m["node_id"] == node_id]
        metric_ids = {m["id"] for m in metrics}
        observations = [o for o in database.all("observation") if o["metric_id"] in metric_ids]
        relationships = [r for r in database.current_relationships() if node_id in (r["from_node"], r["to_node"])]
        hypotheses = [h for h in database.all("hypothesis") if node_id in h["node_ids"]]
        interventions = [i for i in database.all("intervention") if node_id in i["node_ids"]]
        assessments = sorted([a for a in database.all("assessment") if a["node_id"] == node_id],
                             key=lambda a: (a["as_of"], "pressure" in a, a["id"]))
        assessment = assessments[-1] if assessments else None
        evidence_ids = {e for r in relationships for e in r["evidence_ids"] + r.get("counter_evidence_ids", [])}
        evidence_ids.update(e for h in hypotheses for e in h["supporting_evidence_ids"] + h["contradicting_evidence_ids"])
        evidence_ids.update(e for i in interventions for e in i["intent_evidence_ids"] + i["observation_evidence_ids"])
        if assessment:
            evidence_ids.update(assessment["evidence_ids"])
        obs_ids = {o["id"] for o in observations}
        evidence = [e for e in database.all("evidence")
                    if e["id"] in evidence_ids or obs_ids.intersection(e["observation_ids"])]
        statement_ids = {s for e in evidence for s in e["statement_ids"]}
        statement_ids.update(s for h in hypotheses for s in h["institutional_statement_ids"])
        intervention_ids = {i["id"] for i in interventions}
        statements = [s for s in database.all("institutionalstatement")
                      if s["id"] in statement_ids or s["policy_id"] in intervention_ids]
        source_ids = {o["source_id"] for o in observations} | {e["source_id"] for e in evidence}
        sources = [s for s in database.all("source") if s["id"] in source_ids]
        return {"node": node, "metrics": metrics, "observations": observations,
                "relationships": relationships, "assessment": assessment,
                "hypotheses": hypotheses, "interventions": interventions,
                "institutional_statements": statements, "evidence": evidence, "sources": sources}

    @app.get("/api/graph")
    def graph():
        return {"nodes": app.state.store.all("node"), "relationships": app.state.store.current_relationships()}

    @app.get("/api/sources")
    def sources():
        return app.state.store.all("source")

    @app.get("/api/provenance/{entity_type}/{entity_id}")
    def provenance(entity_type: str, entity_id: str):
        aliases = {"raw_snapshot": "rawsnapshot", "institutional_statement": "institutionalstatement"}
        kind = aliases.get(entity_type, entity_type)
        if kind not in MODELS:
            raise HTTPException(404, "unknown entity type")
        return app.state.store.provenance(kind, entity_id)

    @app.post("/api/scenarios/run", response_model=Scenario)
    def scenario(body: ScenarioRequest):
        try:
            return run_scenario(app.state.store, body.node_id, body.shock, body.horizon_months)
        except ScenarioLimitError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get("/")
    def index():
        file = ROOT / "frontend" / "index.html"
        if not file.is_file():
            raise HTTPException(404, "frontend not installed")
        return FileResponse(file)

    app.mount("/static", StaticFiles(directory=str(ROOT / "frontend"), check_dir=False), name="static")
    return app


app = create_app()
