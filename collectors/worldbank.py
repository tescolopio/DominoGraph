"""Allowlisted WDI connector. No credentials, arbitrary URLs, or model inference."""

import json
from datetime import date, datetime, timezone
from hashlib import sha256
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from collectors.base import Collected
from collectors.fred import NoRedirect
from schemas.models import Metric, Node, Observation, Source
from transforms.normalize import snapshot

COUNTRIES = {"US": "United States", "CA": "Canada", "GB": "United Kingdom",
             "DE": "Germany", "JP": "Japan"}
ISO3 = {"US": "USA", "CA": "CAN", "GB": "GBR", "DE": "DEU", "JP": "JPN"}
SERIES = {
    "NY.GDP.MKTP.KD.ZG": {
        "name": "GDP growth", "unit": "% annual growth", "state": "observed",
        "provider": "National statistical organizations, OECD and World Bank staff estimates",
        "description": "Annual change in real gross domestic product. Measures output growth, not the level of GDP."},
    "FP.CPI.TOTL.ZG": {
        "name": "Consumer price inflation", "unit": "% annual change", "state": "observed",
        "provider": "International Monetary Fund, International Financial Statistics",
        "description": "Annual change in consumer prices. Annual data can differ from the latest monthly headline rate."},
    "SL.UEM.TOTL.ZS": {
        "name": "Unemployment", "unit": "% of labor force", "state": "inferred",
        "provider": "International Labour Organization, ILO Modelled Estimates (ILOEST)",
        "description": "Unemployment as a share of the labor force. A modeled ILO estimate, not a monthly national release."},
}
LIMITATIONS = [
    "Annual series; latest reference year may lag the current year.",
    "Original observation publication dates are unavailable; availability begins at local retrieval.",
    "WDI may revise history. Stored vintages reflect local downloads, not an original-release archive.",
    "No calibrated confidence or economic risk score is assigned to imported observations.",
]


class WorldBankCollector:
    def __init__(self, country, indicator):
        if country not in COUNTRIES or indicator not in SERIES:
            raise ValueError("unsupported country or indicator")
        self.country, self.indicator = country, indicator
        self.url = (f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
                    "?format=json&per_page=1000&source=2")

    def collect(self):
        try:
            request = Request(self.url, headers={"User-Agent": "DominoGraph/0.2", "Accept": "application/json"})
            with build_opener(NoRedirect()).open(request, timeout=20) as response:
                body = response.read(2_000_001)
                if len(body) > 2_000_000:
                    raise ValueError("World Bank response exceeds size limit")
                content = body.decode("utf-8")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ValueError("World Bank is unavailable; saved observations are unchanged") from exc
        return Collected(self.url, datetime.now(timezone.utc), content, "worldbank-wdi-v1")


def normalize(raw, country, indicator, existing=()):
    payload = json.loads(raw.content)
    if (not isinstance(payload, list) or len(payload) != 2 or not isinstance(payload[0], dict)
            or not isinstance(payload[1], list)):
        raise ValueError("invalid World Bank response")
    meta, rows = payload
    if int(meta.get("pages", 0)) != 1 or int(meta.get("total", -1)) != len(rows):
        raise ValueError("incomplete World Bank response; refusing partial history")
    if str(meta.get("sourceid")) != "2":
        raise ValueError("unexpected World Bank dataset")
    metric_id = f"wb-{country}-{indicator}"
    prior = {o.id: o for o in existing}
    result, years = [], set()
    for row in rows:
        if row.get("indicator", {}).get("id") != indicator or row.get("countryiso3code") != ISO3[country]:
            raise ValueError("World Bank series/country mismatch")
        year = int(row["date"])
        if year in years:
            raise ValueError("duplicate year in World Bank response")
        years.add(year)
        observed = date(year, 12, 31)
        if row["value"] is None or observed > raw.retrieval_time.date():
            continue
        if isinstance(row["value"], bool) or not isinstance(row["value"], (float, int)):
            raise ValueError("invalid World Bank numeric value")
        identity = "obs-wb-" + sha256(f"{raw.id}:{year}:wdi-normalization-v1".encode()).hexdigest()
        predecessors = sorted((o for o in existing if o.source_id == raw.source_id and o.metric_id == metric_id
                               and o.observation_date == observed and o.retrieval_time <= raw.retrieval_time
                               and o.id != identity), key=lambda o: (o.retrieval_time, o.id))
        result.append(Observation(
            id=identity, metric_id=metric_id, value=row["value"], source_id=raw.source_id,
            source_url=raw.source_url, retrieval_time=raw.retrieval_time,
            publication_date=None, observation_date=observed,
            vintage="WDI dataset update " + str(meta.get("lastupdated", "unknown")),
            collector_version=raw.collector_version, transformation_version="wdi-normalization-v1",
            validation_state="valid", raw_snapshot_id=raw.id,
            normalization_lineage=[f"raw_snapshot:{raw.id}", f"WDI:{indicator}:{country}:{year}",
                                   "Annual period represented by year-end; publication date unknown.",
                                   "Source values retained without scaling; null years omitted."],
            revision_of=prior[identity].revision_of if identity in prior else
            (predecessors[-1].id if predecessors else None),
            confidence=0, evidence_state=SERIES[indicator]["state"]))
    return result


def sync_worldbank(store, country="US", collector_factory=WorldBankCollector):
    if country not in COUNTRIES:
        raise ValueError("unsupported country")
    node = Node(id="macro-" + country, name=COUNTRIES[country] + " economy",
                domain="macroeconomics", geography=country,
                description="Annual macroeconomic indicators from World Development Indicators.")
    pending = [node]
    existing = [Observation.model_validate(o) for o in store.all("observation")]
    saved_raw = store.all("rawsnapshot")
    added = 0
    for indicator, spec in SERIES.items():
        collector = collector_factory(country, indicator)
        source_id = f"source-wb-{country}-{indicator}"
        source = Source(id=source_id, name=f"World Bank WDI · {COUNTRIES[country]} · {spec['name']}",
                        publisher="World Bank; " + spec["provider"], url=collector.url,
                        verification_tier="C", verification_notes="International statistical compilation; tier is not a truth score.",
                        license="CC-BY-4.0", redistribution_allowed=True,
                        license_url="https://data.worldbank.org/indicator/" + indicator,
                        methodology=spec["description"], update_cadence="Annual observations; irregular dataset updates.",
                        revision_policy="Append local snapshots and retain earlier observations; never overwrite.",
                        limitations=LIMITATIONS)
        metric = Metric(id=f"wb-{country}-{indicator}", node_id=node.id, name=spec["name"],
                        dataset=indicator, unit=spec["unit"], frequency="annual",
                        description=spec["description"], context="Exploration only; no pressure-scoring rule assigned.")
        raw = snapshot(collector.collect(), source_id)
        # Reuse an unchanged latest response; an older matching response after an
        # intervening revision must become a new vintage (a source can revert).
        prior_raw = sorted((r for r in saved_raw if r["source_id"] == source_id),
                           key=lambda r: (r["retrieval_time"], r["id"]))
        if prior_raw and prior_raw[-1]["content_sha256"] == raw.content_sha256:
            pending.extend([source, metric])
            continue
        observations = normalize(raw, country, indicator, existing)
        pending.extend([source, metric, raw, *observations])
        added += len(observations)
    # A country refresh is atomic: failed collection/validation retains all old data.
    store.put_many(pending)
    return {"country": country, "series": len(SERIES), "observations_added": added}
