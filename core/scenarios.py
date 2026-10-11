"""Illustrative bounded simple-path propagation; no estimated causal coefficients."""

from hashlib import sha256
import json

from schemas.models import Scenario

MAX_STEPS = 1000
MAX_PATHS = 250


class ScenarioLimitError(ValueError):
    pass


def run_scenario(store, node_id, shock, horizon_months, *, max_steps=MAX_STEPS, max_paths=MAX_PATHS):
    store.get("node", node_id)
    snapshot = store.all("relationship")
    skipped = [{"relationship_id": edge["id"], "reason": "human review: " + edge["review_status"]}
               for edge in snapshot if edge["review_status"] in {"rejected", "needs_revision"}]
    relationships = [edge for edge in snapshot if edge["review_status"] not in {"rejected", "needs_revision"}]
    adjacency = {}
    for edge in relationships:
        adjacency.setdefault(edge["from_node"], []).append(edge)
    steps = paths = 0
    impacts = {node_id: {"node_id": node_id, "illustrative_change_percent": shock,
                        "confidence": 0.0, "paths": [[]]}}
    used = set()
    evidence = set()

    def walk(current, change, elapsed, visited, path, confidence):
        nonlocal steps, paths
        for edge in adjacency.get(current, []):
            steps += 1
            if steps > max_steps:
                raise ScenarioLimitError("illustrative scenario exceeds step limit; use a smaller horizon")
            if edge["to_node"] in visited or edge["direction"] == "ambiguous":
                continue
            lag = elapsed + edge["estimated_lag"]
            if lag > horizon_months:
                continue
            paths += 1
            if paths > max_paths:
                raise ScenarioLimitError("illustrative scenario exceeds path limit; use a smaller horizon")
            sign = 1 if edge["direction"] == "positive" else -1
            delta = change * sign * edge["illustrative_coefficient"]
            target = edge["to_node"]
            next_path = path + [edge["id"]]
            certainty = min(confidence, edge["confidence"])
            item = impacts.setdefault(target, {"node_id": target, "illustrative_change_percent": 0,
                                               "confidence": certainty, "paths": []})
            item["illustrative_change_percent"] = max(-100, min(100, item["illustrative_change_percent"] + delta))
            item["confidence"] = min(item["confidence"], certainty)
            item["paths"].append(next_path)
            used.add(edge["id"])
            evidence.update(edge["evidence_ids"] + edge["counter_evidence_ids"])
            walk(target, delta, lag, visited | {target}, next_path, certainty)

    walk(node_id, shock, 0, {node_id}, [], 1.0)
    identity = sha256(json.dumps([node_id, shock, horizon_months, snapshot],
                                 sort_keys=True).encode()).hexdigest()[:24]
    return Scenario(id="scenario-" + identity, node_id=node_id, shock=shock,
                    horizon_months=horizon_months, impacts=list(impacts.values()),
                    relationship_ids=sorted(used), evidence_ids=sorted(evidence),
                    skipped_relationships=skipped,
                    assumptions=["Shock is an illustrative percent change, not a probability.",
                                 "Multiply sign and explicitly assigned coefficient along simple paths.",
                                 "Sum path contributions, clamp to [-100,100], exclude feedback cycles.",
                                 "Lag is cumulative; paths beyond the requested horizon are omitted.",
                                 f"Hard execution limits: {max_steps} edge steps and {max_paths} accepted path prefixes.",
                                 "Rejected or needs-revision relationships are excluded."],
                    limitations=["SYNTHETIC demo; not a causal forecast or investment recommendation.",
                                 "Coefficients are assumed, not fitted or empirically identified.",
                                 "No substitution, feedback, equilibrium, or exogenous responses modeled.",
                                 "Confidence is weakest-edge evidence confidence, not forecast accuracy."],
                    confidence=min((i["confidence"] for i in impacts.values() if i["paths"] != [[]]), default=0))
