"use strict";
const $ = id => document.getElementById(id);
const number = v => new Intl.NumberFormat(undefined, {maximumFractionDigits: 2, minimumFractionDigits: 2}).format(v);
const dateText = v => v ? new Date(v).toLocaleDateString(undefined, {year: "numeric", month: "short", day: "numeric"}) : "Not available";
const dateTimeText = v => v ? new Date(v).toLocaleString(undefined, {year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit", timeZoneName: "short"}) : "Not recorded";
const node = (tag, text, cls) => {const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n;};
let catalog = [], refreshes = {}, selected = "", detail = null, years = 25, selection = 0, saved = new Set();
try { saved = new Set(JSON.parse(localStorage.getItem("dominograph-saved") || "[]")); } catch {}
function status(text, error = false) { $("status").textContent = text; $("status").classList.toggle("error", error); }
async function request(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(typeof body.detail === "string" ? body.detail : "Unable to load data (" + response.status + ")."); }
  return response.json();
}
function safeLink(label, url) {
  try { if (new URL(url).protocol === "https:") { const a = node("a", label); a.href = url; a.target = "_blank"; a.rel = "noopener noreferrer"; return a; } } catch {}
  return node("span", label);
}
function renderList() {
  const available = catalog.filter(r => r.geography === $("country").value);
  const term = $("search").value.trim().toLowerCase();
  const filtered = available.filter(r => (r.metric.name + " " + r.metric.description).toLowerCase().includes(term) && (!$("saved-only").checked || saved.has(r.metric.id)));
  $("series-count").textContent = available.length;
  $("indicator-list").replaceChildren();
  for (const item of filtered) {
    const button = node("button", undefined, "indicator-card"); button.type = "button"; button.setAttribute("aria-pressed", item.metric.id === selected);
    button.append(node("strong", (saved.has(item.metric.id) ? "★ " : "") + item.metric.name));
    const values = node("span", undefined, "card-values");
    values.append(node("span", item.latest ? number(item.latest.value) + "%" : "—"), node("small", item.latest ? item.latest.observation_date.slice(0,4) : "No data"));
    button.append(values); button.addEventListener("click", () => select(item.metric.id)); $("indicator-list").append(button);
  }
  if (!filtered.length) $("indicator-list").append(node("p", available.length ? "No matching indicators." : "No saved data for this economy yet.", "small muted"));
}
function renderRefresh() {
  const check = refreshes[$("country").value];
  if (!check) throw new Error("Source check status is unavailable. Reload the application.");
  $("check-heading").textContent = "Current workspace source checks / " + $("country").selectedOptions[0].textContent;
  const labels = {fresh: "Source check is fresh.", stale: "Source check is stale; refresh to check for updates.", never_checked: "No successful source check is recorded; refresh to start check history."};
  let text = labels[check.check_status];
  if (!text) throw new Error("Unknown source check status. Reload the application.");
  if (check.latest_run?.status === "failed") text += " Latest refresh failed. " + check.latest_run.error;
  if (check.latest_run?.status === "running") text += " Latest refresh has no recorded completion; it may be running or interrupted.";
  $("check-status").textContent = text;
  $("check-status").classList.toggle("error", check.check_status === "stale" || check.latest_run?.status === "failed");
  $("check-facts").replaceChildren();
  for (const [label, value] of [["Last successful check", check.last_checked_at], ["Last changed snapshot", check.last_changed_at], ["Next check due", check.next_check_due_at]]) {
    const fact = node("div", label); fact.append(node("strong", dateTimeText(value))); $("check-facts").append(fact);
  }
  $("refresh-runs").replaceChildren();
  for (const run of check.recent_runs) {
    const item = node("li"), title = node("strong", run.status + " · Started " + dateTimeText(run.started_at));
    item.append(title);
    if (run.finished_at) item.append(node("p", "Finished " + dateTimeText(run.finished_at) + " · " + run.series_checked + " series checked · " + run.observations_added + " observations added · " + run.snapshots_added + " changed snapshots"));
    else item.append(node("p", "Completion not recorded; this attempt may be running or interrupted."));
    if (run.error) item.append(node("p", run.error, "error"));
    $("refresh-runs").append(item);
  }
  if (!check.recent_runs.length) $("refresh-runs").append(node("li", "No recorded refresh attempts. Existing downloads do not establish a successful check history."));
}
async function loadCatalog(preferred = selected) {
  const data = await request("/api/indicators"); catalog = data.indicators; refreshes = data.refreshes;
  const country = $("country").value; $("country").replaceChildren();
  for (const [id, label] of Object.entries(data.countries)) { const option = node("option", label); option.value = id; $("country").append(option); }
  $("country").value = country || "US";
  renderRefresh();
  const candidates = catalog.filter(r => r.geography === $("country").value);
  const next = candidates.find(r => r.metric.id === preferred) || candidates[0];
  if (next) await select(next.metric.id);
  else {
    selection++; selected = ""; detail = null; $("detail").hidden = true; $("empty").hidden = false; renderList();
    status("No retained indicators for " + $("country").selectedOptions[0].textContent + ". Refresh to check this economy.");
  }
}
async function select(id) {
  selected = id; const version = ++selection; renderList();
  $("detail").hidden = true; $("empty").hidden = true;
  status("Loading retained observations…");
  const cutoff = $("as-of").value;
  try {
    const data = await request("/api/indicators/" + encodeURIComponent(id) + (cutoff ? "?as_of=" + encodeURIComponent(cutoff) : ""));
    if (version !== selection) return;
    detail = data; renderDetail(); $("detail").hidden = false;
    status(cutoff ? "Historical view · downloads retained by " + cutoff + ". Library cards show the latest download." : "Saved data loaded · refresh when you want to check for updates.");
  } catch (error) {if (version === selection) status(error.message, true);}
}
function renderDetail() {
  const {metric, points, sources, snapshots} = detail;
  const last = points.at(-1), previous = points.at(-2);
  $("series-label").textContent = detail.node.geography + " / " + metric.frequency + " / " + metric.dataset;
  $("series-title").textContent = metric.name; $("description").textContent = metric.description;
  $("latest").textContent = last ? number(last.value) + "%" : "—";
  $("latest-period").textContent = last ? "Reference year " + last.observation_date.slice(0,4) : "No observation available in this view";
  const delta = last && previous ? last.value - previous.value : null;
  $("change").textContent = delta === null ? "—" : (delta > 0 ? "+" : "") + number(delta) + " pp";
  $("change-period").textContent = previous ? previous.observation_date.slice(0,4) + " → " + last.observation_date.slice(0,4) + " · percentage points" : "At least two observations needed";
  $("coverage").textContent = points.length ? points[0].observation_date.slice(0,4) + "–" + last.observation_date.slice(0,4) : "No retained data";
  $("save").textContent = saved.has(selected) ? "★ Saved" : "☆ Save indicator"; $("save").setAttribute("aria-pressed", saved.has(selected));
  $("chart-unit").textContent = metric.unit;
  drawChart();
  const source = sources[0];
  $("source-name").textContent = "World Development Indicators";
  $("attribution").textContent = source ? "The World Bank: World Development Indicators: " + source.publisher.replace(/^World Bank; /, "") + "." : "No source available.";
  $("source-method").textContent = source?.methodology || "";
  $("source-links").replaceChildren();
  if (source) $("source-links").append(safeLink("Indicator & license ↗", source.license_url), safeLink("Source data ↗", source.url));
  $("source-facts").replaceChildren();
  const facts = [["Downloaded to this workspace", snapshots.length ? dateText(snapshots[0].retrieval_time) : "No download before this cutoff"], ["Dataset vintage", last?.vintage || "Not available"], ["Original publication date", last?.publication_date || "Not supplied by source"], ["License / retained records", (source?.license || "Unknown") + " · " + detail.retained_observations + " observations"]];
  for (const [label, value] of facts) {const fact = node("div", label); fact.append(node("strong", value)); $("source-facts").append(fact);}
  $("limitations").replaceChildren(...(source?.limitations || []).map(t => node("li", t)));
  $("rows").replaceChildren();
  for (const observation of [...points].reverse()) {
    const row = node("tr"); row.append(node("td", observation.observation_date.slice(0,4)), node("td", number(observation.value) + "%"), node("td", observation.evidence_state === "inferred" ? "Modeled estimate" : "Published statistic"));
    const cell = node("td"), button = node("button", "Inspect source"); button.type = "button";
    button.addEventListener("click", () => inspect(observation)); cell.append(button); row.append(cell); $("rows").append(row);
  }
}
function svgElement(tag, attributes, text) {const e = document.createElementNS("http://www.w3.org/2000/svg", tag); for (const [k,v] of Object.entries(attributes)) e.setAttribute(k, v); if (text !== undefined) e.textContent = text; return e;}
function drawChart() {
  $("chart").replaceChildren();
  document.querySelectorAll("[data-years]").forEach(b => b.setAttribute("aria-pressed", Number(b.dataset.years) === years));
  const lastYear = detail.points.at(-1)?.observation_date.slice(0,4);
  const points = detail.points.filter(p => !years || Number(p.observation_date.slice(0,4)) > Number(lastYear) - years);
  if (!points.length) {$("chart").append(node("p", "No data was downloaded by this date. Choose Latest download or a later date.", "muted")); $("chart-note").textContent = "Historical availability starts when a snapshot is first retrieved."; return;}
  const W = 800, H = 265, left = 54, right = 18, top = 18, bottom = 32;
  const values = points.map(p => p.value), minimum = Math.min(...values), maximum = Math.max(...values), pad = Math.max((maximum - minimum) * .13, .5);
  const lo = minimum - pad, hi = maximum + pad;
  const first = Number(points[0].observation_date.slice(0,4)), last = Number(points.at(-1).observation_date.slice(0,4));
  const x = year => left + (year - first) / Math.max(1, last - first) * (W-left-right);
  const y = value => top + (hi-value)/(hi-lo)*(H-top-bottom);
  const svg = svgElement("svg", {viewBox:"0 0 " + W + " " + H, role:"img", "aria-label":detail.metric.name + ", " + first + " to " + last + ", " + detail.metric.unit + ". Values are listed below."});
  for (let i=0;i<5;i++) {const val = lo + (hi-lo)*i/4; svg.append(svgElement("line", {x1:left,x2:W-right,y1:y(val),y2:y(val),stroke:"#e6eeeb","stroke-dasharray":"3 5"}),svgElement("text", {x:left-10,y:y(val)+4,"text-anchor":"end",fill:"#7c908c","font-size":11},val.toFixed(1)));}
  const tickYears = new Set(Array.from({length:5},(_,i)=>Math.round(first+(last-first)*i/4)));
  for (const year of tickYears) svg.append(svgElement("text", {x:x(year),y:H-5,"text-anchor":"middle",fill:"#7c908c","font-size":11},year));
  let path = "", previous = null;
  for (const p of points) {const year = Number(p.observation_date.slice(0,4)); path += (previous === null || year-previous !== 1 ? "M" : "L") + x(year) + "," + y(p.value) + " "; previous=year;}
  svg.append(svgElement("path", {d:path,fill:"none",stroke:"#168678","stroke-width":2.6,"stroke-linejoin":"round","stroke-linecap":"round"}));
  for (const p of points) {const circle = svgElement("circle", {cx:x(Number(p.observation_date.slice(0,4))),cy:y(p.value),r:3.2,fill:"#168678",stroke:"white","stroke-width":1.5}); circle.append(svgElement("title",{},p.observation_date.slice(0,4) + ": " + number(p.value) + "%")); svg.append(circle);}
  $("chart").append(svg); $("chart-note").textContent = points.length + " annual observations · gaps remain unconnected · axis adapts to this series · changes do not imply improvement or deterioration.";
}
async function inspect(observation) {
  const container = $("evidence-content"); container.replaceChildren();
  const facts=[["Reference year",observation.observation_date.slice(0,4)],["Value",number(observation.value)+"%"],["Downloaded",dateText(observation.retrieval_time)],["Original publication",observation.publication_date || "Not supplied by source"],["Vintage",observation.vintage],["Revision of",observation.revision_of || "First retained version"]];
  for (const [label, value] of facts) {const p=node("p");p.append(node("strong",label+": "),document.createTextNode(value));container.append(p);}
  container.append(safeLink("Open source data ↗", observation.source_url));
  const snapshot = detail.snapshots.find(s => s.id === observation.raw_snapshot_id);
  if (snapshot) container.append(node("p", "Snapshot fingerprint: " + snapshot.content_sha256, "small muted"));
  const disclosure=node("details"),summary=node("summary","Full provenance records"),pre=node("pre","Loading provenance…");disclosure.append(summary,pre);container.append(disclosure);
  $("evidence-dialog").showModal();
  try {pre.textContent=JSON.stringify(await request("/api/provenance/observation/"+encodeURIComponent(observation.id)),null,2);}catch(error){pre.textContent=error.message;}
}
$("country").addEventListener("change", () => {$("as-of").value="";loadCatalog().catch(e=>status(e.message,true));});
$("search").addEventListener("input",renderList);$("saved-only").addEventListener("change",renderList);
$("save").addEventListener("click",()=>{if(!selected)return;saved.has(selected)?saved.delete(selected):saved.add(selected);try{localStorage.setItem("dominograph-saved",JSON.stringify([...saved]));}catch{status("Saved for this session; browser storage is unavailable.");}renderList();renderDetail();});
$("ranges").addEventListener("click",e=>{if(e.target.dataset.years!==undefined){years=Number(e.target.dataset.years);drawChart();}});
$("as-of").addEventListener("change",()=>{if(selected)select(selected);});$("latest-view").addEventListener("click",()=>{$("as-of").value="";if(selected)select(selected);});
$("close-evidence").addEventListener("click",()=>$("evidence-dialog").close());
$("refresh").addEventListener("click",async()=>{
  const button=$("refresh"),country=$("country").value;button.disabled=true;button.textContent="Refreshing…";
  status("Downloading three annual series. Existing history will be preserved…");
  try {
    const result=await request("/api/connectors/worldbank/refresh",{method:"POST",headers:{"Content-Type":"application/json","X-DominoGraph-Request":"1"},body:JSON.stringify({country})});
    await loadCatalog();
    status(country+": "+result.series+" series checked · "+result.observations_added+" observations added. Existing vintages retained.");
  } catch(error) {
    let message=error.message;
    try {await loadCatalog();} catch(historyError) {message+=" Check history could not be reloaded: "+historyError.message;}
    status(message,true);
  } finally {button.disabled=false;button.textContent="↻ Refresh this economy";}
});
loadCatalog().then(()=>{if(!selected)status("Choose an economy and refresh to add your first indicators.");}).catch(error=>status(error.message,true));
