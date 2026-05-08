"use strict";

const tokenInput = document.getElementById("token");
const whoSpan = document.getElementById("who");
const keywaySel = document.getElementById("keyway");
const codeInput = document.getElementById("code");
const result = document.getElementById("result");
const batchInput = document.getElementById("batch-input");
const batchResult = document.getElementById("batch-result");

function getToken() {
  return tokenInput.value || localStorage.getItem("locksmith.token") || "";
}

document.getElementById("save-token").onclick = () => {
  localStorage.setItem("locksmith.token", tokenInput.value);
  whoSpan.textContent = "token saved (local only)";
};
tokenInput.value = localStorage.getItem("locksmith.token") || "";

async function api(path, payload) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: getToken(), ...payload }),
  });
  return res.json();
}

async function loadKeyways() {
  const res = await fetch("/api/keyways");
  const data = await res.json();
  for (const k of data.keyways) {
    const opt = document.createElement("option");
    opt.value = k.keyway;
    opt.textContent = `${k.keyway}  —  ${k.manufacturer} ${k.name} (${k.pin_count} pin, MACS ${k.macs})`;
    keywaySel.appendChild(opt);
  }
}

document.getElementById("decode").onclick = async () => {
  const t0 = performance.now();
  const r = await api("/api/decode", {
    keyway: keywaySel.value,
    code: codeInput.value.trim(),
  });
  const dt = (performance.now() - t0).toFixed(1);
  if (r.error) { result.textContent = `ERROR: ${r.error}`; return; }
  whoSpan.textContent = r.who;
  const b = r.result.bitting;
  if (!b) { result.textContent = `ERROR: ${r.result.error}`; return; }
  const lines = [
    `keyway:       ${b.keyway}  (${b.profile_name})`,
    `manufacturer: ${b.manufacturer}`,
    `bitting:      ${b.bitting.join("-")}`,
    `MACS:         ${b.macs}     valid=${b.valid}`,
    "cuts (in):",
    ...b.inches.map(([s, d], i) =>
      `  pin ${i + 1}:  spacing=${s.toFixed(3)}\"  depth=${d.toFixed(3)}\"`),
  ];
  if (b.issues.length) {
    lines.push("issues:");
    for (const it of b.issues) {
      lines.push(`  - ${it.code}@${it.position}: ${it.detail}`);
    }
  }
  lines.push(`\n(server ${r.result.elapsed_us} us  /  round-trip ${dt} ms)`);
  result.textContent = lines.join("\n");
};

document.getElementById("run-batch").onclick = async () => {
  const text = batchInput.value.trim();
  if (!text) { batchResult.textContent = "paste rows first"; return; }
  const rows = text.split(/\r?\n/).filter(Boolean);
  const start = rows[0].toLowerCase().includes("keyway") ? 1 : 0;
  const jobs = rows.slice(start).map(line => {
    const [keyway, code] = line.split(",").map(s => s.trim());
    return { keyway, code };
  });
  const t0 = performance.now();
  const r = await api("/api/batch", { jobs });
  const dt = (performance.now() - t0).toFixed(1);
  if (r.error) { batchResult.textContent = `ERROR: ${r.error}`; return; }
  whoSpan.textContent = r.who;
  const lines = r.results.map(x => {
    if (!x.ok) return `${x.keyway},${x.code}  ERROR: ${x.error}`;
    return `${x.keyway},${x.code}  ->  ${x.bitting.bitting.join("-")}  (valid=${x.bitting.valid}, ${x.elapsed_us} us)`;
  });
  lines.push(`\n${r.results.length} jobs in ${dt} ms`);
  batchResult.textContent = lines.join("\n");
};

loadKeyways();
