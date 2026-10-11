"""python -m scripts.seed: transactional, repeatable SYNTHETIC pilot bootstrap."""

from datetime import date, datetime, timezone

from collectors.synthetic import SOURCE_URL, SyntheticCollector
from core.scoring import assess
from core.store import Store
from schemas.models import (Evidence, Hypothesis, InstitutionalStatement, Intervention,
                            Metric, Node, Relationship, Source)
from transforms.normalize import normalize_csv, snapshot

NODE_SPECS = [
    ("ai-capex", "AI Capex", "Illustrative hyperscaler investment index."),
    ("hbm-demand", "HBM Demand", "Illustrative high-bandwidth memory demand index."),
    ("memory-capacity", "Memory Capacity Allocation", "Illustrative allocation and inventory pressures."),
    ("consumer-memory", "Consumer Memory Prices", "Illustrative DRAM and NAND price indexes."),
    ("device-prices", "Device Prices", "Unmeasured device price transmission; explicit data gap."),
    ("consumer-demand", "Consumer Demand", "Illustrative PC and smartphone shipment indexes."),
]
METRIC_SPECS = [
    ("dram", "consumer-memory", "DRAM price index", "higher_is_pressure"),
    ("hbm", "hbm-demand", "HBM price index (uncertain demand proxy)", "higher_is_pressure"),
    ("nand", "consumer-memory", "NAND price index", "higher_is_pressure"),
    ("inventory", "memory-capacity", "Memory inventory index", "lower_is_pressure"),
    ("fab-capex", "memory-capacity", "Fabrication capex index", "lower_is_pressure"),
    ("hyperscaler-capex", "ai-capex", "Hyperscaler capex index", "higher_is_pressure"),
    ("pc", "consumer-demand", "PC shipment index", "lower_is_pressure"),
    ("smartphone", "consumer-demand", "Smartphone shipment index", "lower_is_pressure"),
    ("datacenter", "ai-capex", "Datacenter spending index", "higher_is_pressure"),
    ("equipment-spending", "memory-capacity", "Equipment spending index", "lower_is_pressure"),
]


def seed(store: Store):
    store.initialize()
    source = Source(id="synthetic-memory-v1", name="SYNTHETIC DominoGraph pilot CSV",
                    publisher="DominoGraph synthetic demonstration",
                    url=SOURCE_URL, verification_tier="H",
                    verification_notes="Synthetic demonstration, not verified economic facts. Tier is not truth.",
                    license="CC0-1.0", redistribution_allowed=True,
                    license_url="https://creativecommons.org/publicdomain/zero/1.0/", synthetic=True,
                    methodology="Invented indexes for freely redistributable software demonstration.",
                    update_cadence="Fixed pilot fixture; no live updates.",
                    revision_policy="Retain immutable IDs and append linked revisions.",
                    limitations=["No actual measurements, forecast accuracy or causal identification."])
    raw = snapshot(SyntheticCollector().collect(), source.id)
    observations = normalize_csv(raw)
    nodes = [Node(id=i, name=n, domain="memory-and-ai", geography="Global (synthetic)",
                  description=d + " SYNTHETIC: no real-world conclusions.") for i, n, d in NODE_SPECS]
    metrics = [Metric(id=i, node_id=node, name=name, dataset=i, unit="synthetic index (baseline=100)",
                      frequency="monthly", description="SYNTHETIC freely redistributable demo dataset.",
                      baseline=100, scale=50, contextual_direction=direction,
                      context=("HBM price is an uncertain demand proxy: prices do not directly measure demand." if i == "hbm"
                               else "Higher investment/demand/prices increase assumed pressure." if direction == "higher_is_pressure"
                               else "Lower inventory/capacity spending/shipments increase assumed pressure."))
               for i, node, name, direction in METRIC_SPECS]
    evidence = [Evidence(id="evidence-" + o.metric_id, claim=f"SYNTHETIC {o.metric_id} index equals {o.value}.",
                         evidence_state="unverified", kind="observation", polarity="supporting",
                         source_id=source.id, observation_ids=[o.id], statement_ids=[], confidence=.25,
                         limitations=["Synthetic invented observation; cannot establish causality."])
                for o in observations]
    counter = Evidence(id="evidence-counter", claim="SYNTHETIC NAND index rises less than HBM; substitution may weaken transmission.",
                       evidence_state="inferred", kind="observation", polarity="contradicting",
                       source_id=source.id, observation_ids=[next(o.id for o in observations if o.metric_id == "nand")],
                       statement_ids=[], confidence=.2,
                       limitations=["Synthetic counter-evidence illustrates scrutiny, not empirical refutation."])
    edge_metrics = ["hyperscaler-capex", "hbm", "inventory", "dram", "pc"]
    relationships = [
        Relationship(id=f"edge-{index + 1}", from_node=NODE_SPECS[index][0],
                     to_node=NODE_SPECS[index + 1][0],
                     mechanism=mechanism, direction="negative" if index == 4 else "positive",
                     estimated_lag=lag, confidence=.2, evidence_state="inferred",
                     evidence_ids=["evidence-" + edge_metrics[index]],
                     counter_evidence_ids=[counter.id],
                     alternative_explanations=["Substitution, inventory adjustment or unrelated macroeconomic demand may dominate."],
                     evidence_gaps=["Synthetic data cannot identify a causal effect or exclude alternatives."],
                     assumptions=["SYNTHETIC illustrative mechanism; no identified causal effect.",
                                  "Coefficient is a chosen sensitivity, not an empirical estimate."],
                     illustrative_coefficient=coefficient)
        for index, (mechanism, lag, coefficient) in enumerate([
            ("AI investment may raise HBM procurement.", 3, .5),
            ("HBM demand may shift memory capacity allocation.", 6, .4),
            ("Allocation constraints may put pressure on consumer memory prices.", 3, .3),
            ("Component price changes may pass through to device prices.", 3, .2),
            ("Higher device prices may reduce consumer demand.", 3, .3),
        ])
    ]
    policy = Intervention(id="pilot-capacity-policy", node_ids=["memory-capacity"],
                          name="SYNTHETIC capacity support proposal", policy_type="capacity_support",
                          description="Invented proposal; not an enacted real policy.", status="proposed",
                          observation_evidence_ids=[], intent_evidence_ids=["evidence-intent"],
                          limitations=["Intent is not evidence of implementation or economic effect."])
    statement = InstitutionalStatement(
        id="statement-pilot", institution="SYNTHETIC Pilot Institution", speaker="SYNTHETIC spokesperson",
        statement="We propose supporting additional fabrication capacity.",
        statement_date=date(2026, 1, 10), source_id=source.id, source_url=source.url,
        retrieval_time=datetime(2026, 1, 15, tzinfo=timezone.utc),
        intended_outcome="Illustrative capacity expansion", policy_id=policy.id, evidence_state="policy_proposed",
        document="SYNTHETIC demonstration policy note", context="Invented policy example; no actual institution.",
        prediction=None, advocacy="Consider capacity support.", policy_proposal="Capacity support proposal.",
        implemented_policy=None, subsequent_action=None, economic_outcome=None, confidence=.2)
    intent = Evidence(id="evidence-intent", claim="SYNTHETIC institution expresses a capacity-support intention.",
                      evidence_state="policy_proposed", kind="intent", polarity="supporting", source_id=source.id,
                      observation_ids=[], statement_ids=[statement.id], confidence=.2,
                      limitations=["Stated intent cannot establish implemented action or observed outcomes."])
    hypothesis = Hypothesis(
        id="hypothesis-memory-chain", statement="SYNTHETIC AI capex may transmit to consumer demand via memory allocation and prices.",
        node_ids=[n.id for n in nodes], relationship_ids=[r.id for r in relationships],
        dataset_ids=[m.id for m in metrics], policy_ids=[policy.id], institutional_statement_ids=[statement.id],
        supporting_evidence_ids=[e.id for e in evidence], contradicting_evidence_ids=[counter.id],
        evidence_gaps=["No observed device-price dataset.", "No real-world or causally identified observations."],
        falsification_criteria=["Real capacity allocation fails to respond to HBM demand.",
                                "Controlled device-price evidence shows no component price pass-through."],
        falsification_status="untested", confidence=.2, evidence_state="inferred")
    assessments = [assess(node.id, metrics, observations,
                          [e.id for e in evidence if any(o.metric_id in {m.id for m in metrics if m.node_id == node.id}
                                                        and o.id in e.observation_ids for o in observations)] + [counter.id],
                          [r.id for r in relationships if node.id in (r.from_node, r.to_node)],
                          date(2026, 1, 15)) for node in nodes]
    store.put_many([source, raw, *nodes, *metrics, *observations, *evidence, counter,
                    *relationships, policy, statement, intent, hypothesis, *assessments])
    return {"nodes": len(nodes), "metrics": len(metrics), "observations": len(observations),
            "relationships": len(relationships), "label": "SYNTHETIC"}


def main():
    store = Store()
    try:
        print(seed(store))
    finally:
        store.engine.dispose()


if __name__ == "__main__":
    main()
