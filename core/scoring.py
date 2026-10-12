"""pilot-weighted-v1: score = weighted mean of bounded contextual metric scores.

Metric pressure = clamp(50 + sign * 50 * (value-baseline)/scale, 0, 100).
Support, firebreak, dependency and transmission require independent inputs: the
pilot leaves these unmeasured, not inverted pressure. Missing rules produce null,
never a fabricated score. Confidence is weighted observation confidence times 100,
discounted by the fraction of explicitly defined metric weights with valid inputs.
There is intentionally no five-dimension composite.
"""

from datetime import date, timezone
from hashlib import sha256
import json

from schemas.models import Assessment, DIMENSIONS, DimensionResult, Metric, Observation

VERSION = "pilot-weighted-v1"
LIMITATIONS = ["SYNTHETIC demonstration only; no real economic conclusions.",
               "Baseline 100 and scale 50 are illustrative index assumptions.",
               "Support/firebreak/dependency/transmission have no independently measured inputs."]

# Every weight is explicit, version controlled, and normalized only within a dimension.
RULE_WEIGHTS = {
    "pressure": {"dram": .6, "nand": .4, "hbm": 1, "inventory": .5, "fab-capex": .3,
                 "equipment-spending": .2, "hyperscaler-capex": .7, "datacenter": .3, "pc": .5, "smartphone": .5},
    "support": {},
    "dependency": {},
    "firebreak": {},
    "transmission": {},
}


def assess(node_id: str, metrics: list[Metric], observations: list[Observation],
           evidence_ids: list[str], relationship_ids: list[str], as_of: date) -> Assessment:
    metrics = sorted((m for m in metrics if m.node_id == node_id), key=lambda m: m.id)
    latest = {}
    for observation in sorted(observations, key=lambda o: (o.observation_date, o.retrieval_time, o.id)):
        if (observation.validation_state == "valid" and observation.observation_date <= as_of
                and observation.retrieval_time.astimezone(timezone.utc).date() <= as_of):
            latest[observation.metric_id] = observation
    dimensions = {}
    used = set()
    for dimension in DIMENSIONS:
        rules = []
        numerator = certainty = total = 0.0
        ids = []
        expected_weight = sum(RULE_WEIGHTS[dimension].get(m.id, 0) for m in metrics)
        gaps = []
        for metric in sorted(metrics, key=lambda m: m.id):
            weight = RULE_WEIGHTS[dimension].get(metric.id)
            obs = latest.get(metric.id)
            if weight is None or obs is None or metric.baseline is None:
                gaps.append(f"Missing observation or independent {dimension} rule for metric:{metric.id}.")
                continue
            sign = 1 if metric.contextual_direction == "higher_is_pressure" else -1
            pressure = max(0, min(100, 50 + sign * 50 * (obs.value - metric.baseline) / metric.scale))
            score = pressure
            numerator += weight * score
            certainty += weight * obs.confidence
            total += weight
            ids.append(obs.id)
            used.add(obs.id)
            rules.append({"metric_id": metric.id, "observation_id": obs.id, "weight": weight,
                          "baseline": metric.baseline, "scale": metric.scale,
                          "contextual_direction": metric.contextual_direction, "context": metric.context,
                          "formula": "clamp(50+sign*50*(value-baseline)/scale,0,100)",
                          "inverted": False, "metric_score": score})
        dimensions[dimension] = DimensionResult(score=round(numerator / total, 4) if total else None,
                                                confidence=round(100 * certainty / expected_weight, 4) if expected_weight else 0,
                                                observation_ids=ids, rules=rules,
                                                uncertainty=LIMITATIONS + gaps + (["Missing data or rules."] if not total else []))
    confidence = round(sum(d.confidence for d in dimensions.values()) / len(DIMENSIONS), 4)
    identity = sha256(json.dumps(
        {"score_projection": "top-level-v1",
         "dimensions": {key: value.model_dump(mode="json") for key, value in dimensions.items()},
         "metrics": [m.model_dump(mode="json") for m in metrics],
         "observations": [latest[m.id].model_dump(mode="json") for m in metrics
                          if m.id in latest and latest[m.id].id in used],
         "evidence_ids": sorted(evidence_ids), "relationship_ids": sorted(relationship_ids)},
        sort_keys=True).encode()).hexdigest()[:16]
    return Assessment(id=f"assessment-{node_id}-{as_of}-{VERSION}-{identity}", node_id=node_id,
                      as_of=as_of, scoring_version=VERSION, dimensions=dimensions,
                      **{name: dimensions[name].score for name in DIMENSIONS},
                      metric_ids=[m.id for m in metrics], observation_ids=sorted(used),
                      relationship_ids=sorted(relationship_ids),
                      evidence_ids=sorted(evidence_ids),
                      confidence=confidence, limitations=LIMITATIONS)
