"use strict";

const byId = (id) => document.getElementById(id);
let selectedNode = "";
let selectionVersion = 0;
let graph = { nodes: [], relationships: [] };

async function request(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`Request failed (${response.status}). Check that the database is seeded.`);
  return response.json();
}

function element(tag, text, className) {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (className) item.className = className;
  return item;
}

function displayJSON(id, value) {
  byId(id).textContent = JSON.stringify(value, null, 2);
}

function traceButton(type, id, label = "Trace to sources") {
  const button = element("button", label);
  button.type = "button";
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      displayJSON("trace", await request(`/api/provenance/${encodeURIComponent(type)}/${encodeURIComponent(id)}`));
      byId("trace").focus();
    } catch (error) {
      byId("status").textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
  return button;
}

function article(container, title, record, type) {
  const card = element("article");
  card.append(element("h4", title), element("pre", JSON.stringify(record, null, 2)));
  if (type && record.id) card.append(traceButton(type, record.id));
  container.append(card);
}

function drawGraph() {
  byId("graph").replaceChildren();
  for (const node of graph.nodes) {
    const button = element("button", node.name, "graph-node");
    button.type = "button";
    button.setAttribute("aria-pressed", String(node.id === selectedNode));
    const downstream = graph.relationships.filter((edge) => edge.from_node === node.id);
    for (const edge of downstream) {
      const target = graph.nodes.find((item) => item.id === edge.to_node);
      button.append(element("small", ` → ${target ? target.name : edge.to_node} (${edge.evidence_state}; confidence ${edge.confidence} / 1)`));
    }
    for (const edge of graph.relationships.filter((item) => item.to_node === node.id)) {
      const source = graph.nodes.find((item) => item.id === edge.from_node);
      button.append(element("small", ` ← ${source ? source.name : edge.from_node} (${edge.evidence_state}; confidence ${edge.confidence} / 1)`));
    }
    button.addEventListener("click", () => selectNode(node.id));
    byId("graph").append(button);
  }
}

async function selectNode(id) {
  const version = ++selectionVersion;
  selectedNode = id;
  byId("node").value = id;
  byId("details").hidden = true;
  byId("scenario-result").textContent = "";
  drawGraph();
  if (!id) return;
  byId("status").textContent = "Loading node…";
  try {
    const data = await request(`/api/nodes/${encodeURIComponent(id)}`);
    if (version !== selectionVersion) return;
    byId("node-title").textContent = data.node.name;
    byId("node-description").textContent = data.node.description;
    byId("dimensions").replaceChildren();
    byId("assessment-meta").replaceChildren();
    const assessment = data.assessment;
    for (const name of ["pressure", "firebreak", "support", "dependency", "transmission", "confidence"]) {
      const card = element("div", name, "dimension");
      const value = assessment ? (name === "confidence" ? assessment.confidence :
        assessment.dimensions?.[name]?.score) : null;
      card.append(element("strong", typeof value === "number" ? `${value} / 100` : "Not assessed"));
      if (typeof value === "number") {
        const meter = element("meter");
        meter.min = 0;
        meter.max = 100;
        meter.value = value;
        meter.setAttribute("aria-label", name);
        card.append(meter);
      }
      byId("dimensions").append(card);
    }
    const oldTrace = byId("assessment-trace");
    if (assessment) {
      const nextTrace = traceButton("assessment", assessment.id, "Trace assessment to sources");
      nextTrace.id = "assessment-trace";
      oldTrace.replaceWith(nextTrace);
      byId("assessment-meta").append(element("pre", JSON.stringify(assessment, null, 2)));
    } else {
      oldTrace.hidden = true;
    }
    byId("metrics").replaceChildren();
    for (const metric of data.metrics) {
      const observations = data.observations.filter((observation) => observation.metric_id === metric.id);
      if (!observations.length) {
        const row = element("tr");
        for (const text of [metric.name, "Missing observation", "—", "—", "—"]) row.append(element("td", text));
        const cell = element("td");
        cell.append(traceButton("metric", metric.id));
        row.append(cell);
        byId("metrics").append(row);
      }
      for (const observation of observations) {
        const row = element("tr");
        for (const text of [metric.name, `${observation.value} ${metric.unit}`, observation.observation_date,
          observation.vintage, observation.validation_state]) row.append(element("td", text));
        const cell = element("td");
        cell.append(traceButton("observation", observation.id));
        row.append(cell);
        byId("metrics").append(row);
      }
    }
    for (const key of ["relationships", "interventions", "institutional_statements", "hypotheses", "evidence", "sources"]) {
      const container = byId(key);
      container.replaceChildren();
      const records = data[key] || [];
      if (!records.length) container.append(element("p", "No records. This is an explicit evidence gap."));
      for (const record of records) {
        const type = { relationships: "relationship", interventions: "intervention",
          institutional_statements: "institutional_statement", hypotheses: "hypothesis",
          evidence: "evidence", sources: "source" }[key];
        article(container, record.name || record.claim || record.statement || record.mechanism || record.id, record, type);
      }
    }
    byId("details").hidden = false;
    byId("status").textContent = "Synthetic pilot loaded. Inspect evidence before drawing conclusions.";
  } catch (error) {
    if (version === selectionVersion) byId("status").textContent = error.message;
  }
}

byId("node").addEventListener("change", (event) => selectNode(event.target.value));
byId("scenario").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedNode) return;
  const version = selectionVersion;
  const button = event.target.querySelector("button");
  button.disabled = true;
  try {
    const result = await request("/api/scenarios/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ node_id: selectedNode, shock: Number(byId("shock").value),
        horizon_months: Number(byId("horizon").value) })
    });
    if (version === selectionVersion) displayJSON("scenario-result", result);
  } catch (error) {
    byId("status").textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

(async () => {
  try {
    const [nodes, graphData] = await Promise.all([request("/api/nodes"), request("/api/graph")]);
    graph = graphData;
    for (const node of nodes) {
      const option = element("option", node.name);
      option.value = node.id;
      byId("node").append(option);
    }
    drawGraph();
    if (nodes.length) {
      const pilot = nodes.find((node) => node.id === "D-MEM-001") || nodes[0];
      await selectNode(pilot.id);
    } else {
      byId("status").textContent = "No nodes yet. Run python -m scripts.seed, then reload.";
    }
  } catch (error) {
    byId("status").textContent = error.message;
  }
})();
