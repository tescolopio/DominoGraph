"""Read-only indicator views plus explicit, same-origin local refresh."""
from datetime import date, datetime
from threading import Lock
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from collectors.worldbank import COUNTRIES, sync_worldbank

router = APIRouter(prefix="/api")
refresh_lock = Lock()


def selected_history(store, metric_id, as_of=None):
    records = [o for o in store.all("observation") if o["metric_id"] == metric_id]
    source_ids = {o["source_id"] for o in records}
    # Each WDI source belongs to one series. Select the complete source snapshot
    # before selecting observations so a withdrawn/null value cannot reappear.
    latest = {}
    for raw in store.all("rawsnapshot"):
        if raw["source_id"] not in source_ids:
            continue
        instant = datetime.fromisoformat(raw["retrieval_time"])
        if as_of and instant.date() > as_of:
            continue
        key = (instant, raw["id"])
        if raw["source_id"] not in latest or key > latest[raw["source_id"]][0]:
            latest[raw["source_id"]] = (key, raw)
    raw_ids = {r[1]["id"] for r in latest.values()}
    points = [o for o in records if o["raw_snapshot_id"] in raw_ids and o["validation_state"] == "valid"
              and (not as_of or o["observation_date"] <= as_of.isoformat())]
    points.sort(key=lambda o: (o["observation_date"], o["source_id"], o["id"]))
    return points, [r[1] for r in latest.values()], records


@router.get("/indicators")
def indicators(request: Request):
    store = request.app.state.store
    nodes = {n["id"]: n for n in store.all("node")}
    sources = {s["id"]: s for s in store.all("source")}
    observations = store.all("observation")
    result = []
    for metric in store.all("metric"):
        source_ids = {o["source_id"] for o in observations if o["metric_id"] == metric["id"]}
        if not source_ids or any(sources[s]["synthetic"] for s in source_ids):
            continue
        points, snapshots, _ = selected_history(store, metric["id"])
        last = points[-1] if points else None
        previous = points[-2] if len(points) > 1 else None
        result.append({"metric": metric, "geography": nodes[metric["node_id"]]["geography"],
                       "latest": last, "previous": previous, "count": len(points),
                       "retrieved_at": max((s["retrieval_time"] for s in snapshots), default=None)})
    return {"indicators": result, "countries": COUNTRIES}


@router.get("/indicators/{metric_id}")
def indicator(metric_id: str, request: Request, as_of: date | None = None):
    store = request.app.state.store
    metric = store.get("metric", metric_id)
    points, snapshots, records = selected_history(store, metric_id, as_of)
    sources = [store.get("source", identity) for identity in sorted({o["source_id"] for o in records})]
    return {"metric": metric, "node": store.get("node", metric["node_id"]), "points": points,
            "sources": sources, "as_of": as_of,
            "snapshots": [{k: s[k] for k in ("id", "source_id", "retrieval_time", "content_sha256", "collector_version")}
                          for s in snapshots],
            "retained_observations": len(records)}


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    country: Literal["US", "CA", "GB", "DE", "JP"] = "US"


@router.post("/connectors/worldbank/refresh")
def refresh(body: RefreshRequest, request: Request):
    origin = request.headers.get("origin")
    if (request.headers.get("x-dominograph-request") != "1"
            or (origin and origin != str(request.base_url).rstrip("/"))):
        raise HTTPException(403, "Refresh must be requested from this application")
    if not refresh_lock.acquire(blocking=False):
        raise HTTPException(409, "A refresh is already running; try again shortly")
    try:
        return sync_worldbank(request.app.state.store, body.country)
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise HTTPException(502, "Refresh failed. Previously saved data is unchanged. Try again later.") from exc
    finally:
        refresh_lock.release()
