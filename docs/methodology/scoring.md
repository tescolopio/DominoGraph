# Scoring methodology: pilot-weighted-v1

This is an invented demonstration, not a calibrated economic risk model.
Expose Pressure, Firebreak, Support, Dependency, Transmission, and Confidence
independently. Do not compute a composite. Dimension scores and assessment
confidence use 0–100; observation and relationship confidence use 0–1.

## Contextual pressure formula

For a metric with explicitly documented baseline `b`, positive scale `s`, value
`x`, and contextual sign `d`:

```text
d = +1 for higher_is_pressure, −1 for lower_is_pressure
metric_pressure = clamp(50 + d × 50 × (x − b) / s, 0, 100)
node_pressure = sum(weight × metric_pressure) / sum(available weights)
```

Baseline 100 and scale 50 in the sample are illustrative index assumptions.
Rising inventories or shipments may reduce the defined pressure while rising
input prices may increase it; direction alone never determines economic meaning.
Weights are explicit in `core/scoring.py` and copied into assessment rules alongside
baseline, scale, context, observation IDs, and metric scores.

## Missing dimensions and uncertainty

Do not derive institutional Support, natural Firebreak, support Dependency, or
Transmission merely by inverting pressure. These require independently defined
and evidenced inputs. The initial pilot leaves unmeasured dimensions `null` and
explains the gaps, instead of asserting invented buffers or policy support.
`null` is not zero. Confidence describes evidence completeness/quality, not a
probability of crisis, forecast accuracy, or propagation elasticity.

For each dimension, confidence is `100 × sum(available weight × observation
confidence) / sum(expected metric weights)`. Missing inputs therefore reduce
confidence. A dimension without rules has confidence zero. Assessment confidence
is the arithmetic mean of the five dimension confidences: it describes overall
coverage, not a composite economic risk score.

Use only validated observations available by the assessment date, retaining the
exact chosen vintage/observation IDs. Missing metrics must be disclosed even when
other metrics allow a partial pressure score. Never backfill historical assessments
with information retrieved later without creating a new assessment identity.

## Reproduction and review

Retain schema, collector, transformation, methodology, and scoring versions, raw
snapshot hashes, observations, and rule inputs. Changes to formulas, weights,
baselines, contextual directions, or missing-data policy require a new scoring
version and human review. Preserve previous assessments rather than overwrite them.

Tests should cover bounded scores, contextual direction, missing data, as-of
selection, and retained revisions. Before real economic use, publish calibration,
source limitations, sensitivity analysis, out-of-sample validation, and falsification
criteria. The synthetic demo cannot establish empirical accuracy.
