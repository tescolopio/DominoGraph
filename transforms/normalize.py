import csv
import io
from hashlib import sha256

from collectors.base import Collected
from schemas.models import Observation, RawSnapshot


def snapshot(collection: Collected, source_id: str) -> RawSnapshot:
    digest = sha256(collection.content.encode()).hexdigest()
    identity = sha256((source_id + collection.retrieval_time.isoformat() + digest).encode()).hexdigest()
    return RawSnapshot(id="raw-" + identity, source_id=source_id,
                       source_url=collection.source_url, retrieval_time=collection.retrieval_time,
                       content_sha256=digest, content=collection.content,
                       collector_version=collection.collector_version)


def normalize_csv(raw: RawSnapshot, existing_observations=(), transformation_version="csv-normalization-v1") -> list[Observation]:
    existing_observations = tuple(existing_observations)
    by_id = {o.id: o for o in existing_observations}
    rows = csv.DictReader(io.StringIO(raw.content))
    required = {"metric_id", "value", "observation_date", "publication_date", "vintage"}
    if not required <= set(rows.fieldnames or []):
        raise ValueError("missing required CSV columns")
    result = []
    for number, row in enumerate(rows, start=2):
        identity = sha256((raw.id + ":" + str(number) + ":" + transformation_version).encode()).hexdigest()
        existing = by_id.get("obs-" + identity)
        prior = sorted((o for o in existing_observations
                        if o.id != "obs-" + identity and o.source_id == raw.source_id
                        and o.metric_id == row["metric_id"] and str(o.observation_date) == row["observation_date"]
                        and o.retrieval_time <= raw.retrieval_time),
                       key=lambda o: (o.retrieval_time, o.id))
        result.append(Observation(
            id="obs-" + identity, metric_id=row["metric_id"], value=float(row["value"]),
            source_id=raw.source_id, source_url=raw.source_url, retrieval_time=raw.retrieval_time,
            publication_date=row["publication_date"], observation_date=row["observation_date"],
            vintage=row["vintage"], collector_version=raw.collector_version,
            transformation_version=transformation_version, validation_state="valid",
            revision_of=existing.revision_of if existing else (prior[-1].id if prior else None),
            raw_snapshot_id=raw.id, normalization_lineage=[
                f"raw_snapshot:{raw.id}", f"csv_row:{number}",
                f"transformation:{transformation_version}", "value:float;unit:metric-defined"],
            confidence=0.25, evidence_state="unverified"))
    return result
