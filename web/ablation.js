/* Replay only. No browser-generated physics or invented flow vectors. */
const $ = (id) => document.getElementById(id);
const escapeText = (value) => String(value).replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[c]));
const svgText = escapeText;
const avg = (values) => values.reduce((a, b) => a + b, 0) / values.length;
const fmt = (value, decimals = 0) => Number(value).toFixed(decimals);
const color = {a: "#60e0c6", b: "#ffc478"};
let artifact, objectiveReport = null, selected = 0, step = 0, timer = null;

function currentEpisode() { return artifact.episodes[selected]; }
function policy(which) { return $(which + "Policy").value; }
function run(which) { return currentEpisode().policies[policy(which)]; }
function state(which) {
  const episode = currentEpisode();
  if (step === 0) return episode.origin;
  const frame = run(which).frames[step - 1];
  return {co2_ppm: frame.co2_ppm, opening_pct: frame.opening_pct};
}
function planSvg(which) {
  const episode = currentEpisode(), topology = episode.topology;
  const zones = topology.zones, openings = topology.openings, values = state(which);
  const n = zones.length, gap = 12, width = (470 - (n - 1) * gap) / n;
  const zoneIndex = Object.fromEntries(zones.map((zone, i) => [zone.id, i]));
  const rects = zones.map((zone, i) => {
    const x = 15 + i * (width + gap), co2 = values.co2_ppm[zone.id];
    const tint = co2 > 1200 ? "#422e2a" : "#1b3740";
    return `<rect x="${x}" y="36" width="${width}" height="100" rx="5" fill="${tint}" stroke="#607b87"/>
      <text x="${x + width / 2}" y="82" font-size="11" fill="#e7f2f5" text-anchor="middle">${svgText(zone.id)}</text>
      <text x="${x + width / 2}" y="99" font-size="10" fill="#9fb4c3" text-anchor="middle">${fmt(co2)} ppm</text>`;
  });
  const windowRects = openings.filter((edge) => edge.kind === "window").map((edge) => {
    const zone = edge.source === topology.outside_id ? edge.target : edge.source;
    const i = zoneIndex[zone];
    if (i === undefined) return "";
    const x = 15 + i * (width + gap), pct = Number(values.opening_pct[edge.id] || 0);
    const length = Math.max(3, (width - 12) * pct / 100);
    return `<rect x="${x + 6}" y="36" width="${width - 12}" height="5" rx="2" fill="#354958"/>
      <rect x="${x + 6}" y="36" width="${length}" height="5" rx="2" fill="${color[which]}"/>
      <text x="${x + width / 2}" y="24" text-anchor="middle" font-size="10" fill="${color[which]}">${svgText(edge.id)} ${fmt(pct)}%</text>`;
  });
  const doors = openings.filter((edge) => edge.kind === "door").map((edge) => {
    const left = zoneIndex[edge.source], right = zoneIndex[edge.target];
    if (left === undefined || right === undefined) return "";
    const x1 = 15 + left * (width + gap) + width / 2;
    const x2 = 15 + right * (width + gap) + width / 2;
    const pct = Number(values.opening_pct[edge.id] || 0);
    const mid = (x1 + x2) / 2, arcY = 163 + 7 * Math.abs(right - left);
    return `<path d="M ${x1} 140 Q ${mid} ${arcY} ${x2} 140" fill="none" stroke="${pct > 0 ? color[which] : "#526572"}" stroke-width="3"/>
      <text x="${mid}" y="${arcY - 5}" text-anchor="middle" font-size="8" fill="#9fb4c3">${svgText(edge.id)}</text>
      <title>${svgText(edge.id)}: ${fmt(pct)}%</title>`;
  });
  return [...rects, ...doors, ...windowRects].join("");
}
function metricHtml(runData, which) {
  const m = runData.metrics, current = state(which);
  const co2 = avg(Object.values(current.co2_ppm));
  const frame = step > 0 ? runData.frames[step - 1] : null;
  const rows = [
    ["Current mean CO₂", fmt(co2) + " ppm"],
    ["Full replay excess", fmt(m.mean_co2_excess_ppm, 1) + " ppm"],
    ["Full replay worst peak", fmt(m.worst_zone_peak_co2_ppm) + " ppm"],
    ["Total actuator movement", fmt(m.total_window_and_door_motion_pct) + "%"],
    ["Safety interventions", String(m.safety_intervention_steps)],
    ["Current intervention", frame?.intervention || "None"],
  ];
  return rows.map(([name, value]) => `<div class="metric"><span>${escapeText(name)}</span><b>${escapeText(value)}</b></div>`).join("");
}
function chartSvg() {
  const ep = currentEpisode();
  const left = [ep.origin.co2_ppm, ...run("left").frames.map((f) => f.co2_ppm)].map((row) => avg(Object.values(row)));
  const right = [ep.origin.co2_ppm, ...run("right").frames.map((f) => f.co2_ppm)].map((row) => avg(Object.values(row)));
  const min = Math.min(...left, ...right, 1000) - 70, max = Math.max(...left, ...right, 1000) + 70;
  const x = (i) => 55 + i / (left.length - 1) * 710;
  const y = (v) => 207 - (v - min) / (max - min) * 177;
  const points = (arr) => arr.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const ticks = [min, (min + max) / 2, max];
  const grid = ticks.map((v) => `<line x1="55" y1="${y(v)}" x2="765" y2="${y(v)}" stroke="#345060" stroke-width=".8"/>
    <text x="47" y="${y(v) + 4}" text-anchor="end" fill="#9fb4c3" font-size="11">${fmt(v)}</text>`).join("");
  return `${grid}
    <line x1="55" y1="${y(1000)}" x2="765" y2="${y(1000)}" stroke="#9fb4c3" stroke-dasharray="6 5"/>
    <polyline points="${points(left)}" fill="none" stroke="${color.a}" stroke-width="3"/>
    <polyline points="${points(right)}" fill="none" stroke="${color.b}" stroke-width="3"/>
    <line x1="${x(step)}" y1="30" x2="${x(step)}" y2="207" stroke="#ffffff" stroke-opacity=".65" stroke-dasharray="3 4"/>
    <circle cx="${x(step)}" cy="${y(left[step])}" r="5" fill="${color.a}"/>
    <circle cx="${x(step)}" cy="${y(right[step])}" r="5" fill="${color.b}"/>
    <text x="55" y="231" font-size="11" fill="#9fb4c3">t=0</text>
    <text x="765" y="231" font-size="11" fill="#9fb4c3" text-anchor="end">t=${left.length - 1} min</text>`;
}
function renderObjective() {
  if (!objectiveReport) return;
  const item = objectiveReport.episodes[selected];
  if (!item || item.scenario_id !== currentEpisode().scenario_id) {
    $("objectiveSummary").textContent = "Objective receipt does not match the selected backend scenario.";
    return;
  }
  const decision = item.decision;
  const recommended = new Set(decision.recommended);
  const rows = decision.results.map((r) => {
    const m = r.metrics;
    return `<tr>
      <td class="${recommended.has(r.label) ? "selected" : ""}">${escapeText(r.label)}</td>
      <td>${escapeText(fmt(m.co2_excess, 1))} ppm</td>
      <td>${escapeText(fmt(m.movement, 1))}%</td>
      <td>${escapeText(r.feasible ? "FEASIBLE" : r.hard_violations.join("; "))}</td>
    </tr>`;
  }).join("");
  $("objectiveSummary").innerHTML = `
    <p><b>Backend:</b> ${escapeText(decision.results[0].provenance.backend)}
    · <b>Objective:</b> CO₂ below 1,000 ppm
    · <b>Horizon:</b> 1 minute
    · <b>Physical execution:</b> NOT AUTHORIZED</p>
    <p><b>Lowest feasible lexicographic penalty:</b>
    ${escapeText(decision.recommended.length ? decision.recommended.join(", ") : "NONE")}
    · <b>Status:</b> ${escapeText(decision.status)}</p>
    <table class="comparison-table">
      <thead><tr><th>Policy</th><th>CO₂ excess</th><th>Opening motion</th><th>Hard constraints</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p>Not scored: ${escapeText(item.unavailable_metric_fields.join(", "))}.
    Same-origin fingerprint: <code>${escapeText(decision.origin_sha256.slice(0, 16))}…</code></p>`;
}
function render() {
  if (!artifact) return;
  const ep = currentEpisode();
  $("step").max = ep.horizon_steps;
  $("step").value = step;
  $("stepValue").textContent = `${step} / ${ep.horizon_steps} min`;
  for (const which of ["left", "right"]) {
    $(which + "Title").textContent = policy(which);
    $(which + "Plan").innerHTML = planSvg(which);
    $(which + "Metrics").innerHTML = metricHtml(run(which), which);
  }
  $("co2Chart").innerHTML = chartSvg();
  renderObjective();
  $("provenance").innerHTML = `
    <p><b>Origin SHA-256:</b> <code>${escapeText(ep.origin_sha256)}</code></p>
    <p><b>Artifact SHA-256:</b> <code>${escapeText(artifact.artifact_sha256)}</code></p>
    <p><b>Physics:</b> ${escapeText(artifact.evaluation.physics_backend)}
    · <b>Training:</b> ${escapeText(artifact.training.data_source)}
    · <b>Train:</b> 2–4 room chain · <b>Test:</b> ${escapeText(ep.topology_family)} five-room graph
    · <b>Toy structural holdout:</b> ${artifact.evaluation.structural_family_holdout ? "YES" : "NO"}</p>
    <p>${escapeText(artifact.claim_boundary)}</p>`;
}
function stop() {
  if (timer !== null) clearInterval(timer);
  timer = null;
  $("play").textContent = "▶ Play";
}
function reset() { stop(); step = 0; render(); }
function play() {
  if (timer !== null) { stop(); return; }
  if (step >= currentEpisode().horizon_steps) step = 0;
  $("play").textContent = "Ⅱ Pause";
  timer = setInterval(() => {
    step += 1;
    render();
    if (step >= currentEpisode().horizon_steps) stop();
  }, 500);
}
function bind() {
  $("episode").addEventListener("change", () => { selected = Number($("episode").value); reset(); });
  for (const which of ["left", "right"]) $(which + "Policy").addEventListener("change", render);
  $("step").addEventListener("input", () => { stop(); step = Number($("step").value); render(); });
  $("play").addEventListener("click", play);
  $("reset").addEventListener("click", reset);
}
async function main() {
  try {
    const response = await fetch("./data/toy_ablation.json", {cache: "no-store"});
    if (!response.ok) throw new Error("Artifact unavailable (HTTP " + response.status + ")");
    artifact = await response.json();
    if (artifact.schema_version !== "airtrajectory-toy-ablation-v0.1"
        || artifact.status !== "EXPLORATORY_NOT_ENGINEERING_TRUTH"
        || artifact.evaluation.physics_backend !== "toy-scenario-v1"
        || artifact.evaluation.structural_family_holdout !== false
        || !artifact.episodes?.length) {
      throw new Error("Unexpected artifact schema or evidence boundary");
    }
    try {
      const comparisonResponse = await fetch("./data/toy_objective_comparison.json", {cache: "no-store"});
      if (!comparisonResponse.ok) throw new Error("Objective receipt unavailable");
      const receipt = await comparisonResponse.json();
      if (receipt.schema_version !== "0.1"
          || receipt.status !== "TOY_CO2_ONLY_NOT_ENGINEERING_TRUTH"
          || receipt.execution_authorized !== false
          || receipt.source_artifact_sha256 !== artifact.artifact_sha256
          || receipt.episodes?.length !== artifact.episodes.length
          || receipt.episodes.some((item, i) => item.scenario_id !== artifact.episodes[i].scenario_id
              || item.observed_metric_fields?.join(",") !== "co2_ppm"
              || item.execution_authorized !== false)) {
        throw new Error("Objective receipt does not match verified replay artifact");
      }
      objectiveReport = receipt;
    } catch (error) {
      $("objectiveSummary").textContent = "Objective diagnostic unavailable: " + error.message;
    }
    $("episode").innerHTML = artifact.episodes.map((ep, i) =>
      `<option value="${i}">${escapeText(ep.scenario_id)}</option>`).join("");
    for (const which of ["left", "right"]) {
      $(which + "Policy").innerHTML = artifact.evaluation.policies.map((name) =>
        `<option value="${escapeText(name)}">${escapeText(name)}</option>`).join("");
    }
    $("leftPolicy").value = "Rule Joint";
    $("rightPolicy").value = "BC";
    $("loading").hidden = true;
    $("lab").hidden = false;
    bind();
    render();
  } catch (error) {
    $("loading").textContent = `Cannot load verified replay artifact: ${error.message}. Run python examples/export_toy_ablation.py or use the deployed Pages build.`;
  }
}
main();
