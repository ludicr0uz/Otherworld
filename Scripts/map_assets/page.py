"""The page: every scanned mesh in one sortable table. No `unreal` import.

One self-contained file: the scan is embedded as JSON, because a page opened
from disk may not fetch a file beside it. The page filters and sorts in the
browser: a tab per category (kinds.CATEGORIES; the ones with a mesh), and
within it a chip per kind.

A mesh's picture is a file in the folder beside the page (shade.py writes
them; ``thumbs`` is {path: file name}), so the page and that folder move
together. A mesh without one gets an empty tile.

A click on a picture opens it large, and there the mesh turns: its turn is
one strip of view.SPIN_FRAMES frames side by side (``spins`` is {path: file
name}, in the other folder beside the page), shown a frame at a time as the
pointer drags. A mesh with a picture and no strip is shown still.

A mesh's bar is its triangles against the heaviest mesh on show, so the bars
rescale with the filter.
"""

import json
import os

from map_assets.kinds import CATEGORIES, classify, pack_of
from map_assets.paths import PAGE_HTML, SCAN_JSON, SPIN_DIR, THUMB_DIR
from map_assets.view import SPIN_FRAMES

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Otherworld assets</title>
<style>
:root {
  --bg: #f4f3ef; --panel: #fffefb; --ink: #1d1f1c; --muted: #6b7068; --line: #dddbd3;
  --accent: #2f6b45; --accent-soft: #dcebe0; --bar: #7fae8d; --nanite: #8a5a14;
  --nanite-soft: #f4e6cc; --row: #f0efe9;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #151714; --panel: #1d201c; --ink: #e6e8e2; --muted: #969c92; --line: #30342e;
    --accent: #86c79b; --accent-soft: #24382b; --bar: #4f8a62; --nanite: #e2b566;
    --nanite-soft: #3b2f17; --row: #232722;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
header { padding: 20px 24px 0; }
h1 { margin: 0; font-size: 20px; font-weight: 650; letter-spacing: -0.01em; }
.sub { color: var(--muted); margin-top: 2px; }
.sub code { font: 12px ui-monospace, Menlo, monospace; }
.stats { display: flex; flex-wrap: wrap; gap: 28px; margin: 16px 0 4px; }
.stat b { display: block; font-size: 22px; font-weight: 650; font-variant-numeric: tabular-nums; }
.stat span { color: var(--muted); font-size: 12px; }
.controls { position: sticky; top: 0; z-index: 2; background: var(--bg);
  padding: 12px 24px; border-bottom: 1px solid var(--line);
  display: flex; flex-wrap: wrap; gap: 10px 14px; align-items: center; }
input[type=search], select { font: inherit; color: var(--ink); background: var(--panel);
  border: 1px solid var(--line); border-radius: 6px; padding: 6px 10px; }
input[type=search] { width: 260px; }
label.check { display: inline-flex; gap: 6px; align-items: center; color: var(--muted);
  cursor: pointer; user-select: none; }
.tabs { display: flex; flex-wrap: wrap; gap: 4px; flex-basis: 100%; }
.tab { font: inherit; font-weight: 600; color: var(--muted); background: none; border: 0;
  border-bottom: 2px solid transparent; padding: 4px 10px 6px; cursor: pointer; }
.tab i { font-style: normal; font-weight: 400; margin-left: 5px;
  font-variant-numeric: tabular-nums; }
.tab[aria-selected=true] { color: var(--ink); border-bottom-color: var(--accent); }
.tab:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; flex-basis: 100%; }
.chip { font: inherit; font-size: 13px; color: var(--ink); background: var(--panel);
  border: 1px solid var(--line); border-radius: 999px; padding: 3px 11px; cursor: pointer; }
.chip i { font-style: normal; color: var(--muted); margin-left: 5px;
  font-variant-numeric: tabular-nums; }
.chip[aria-pressed=true] { background: var(--accent-soft); border-color: var(--accent); }
.chip:focus-visible, th button:focus-visible, td.name button:focus-visible {
  outline: 2px solid var(--accent); outline-offset: 2px; }
.wrap { padding: 0 24px 40px; overflow-x: auto; }
table { border-collapse: collapse; width: 100%; min-width: 1060px; }
th { text-align: left; font-weight: 600; font-size: 12px; color: var(--muted);
  border-bottom: 1px solid var(--line); padding: 10px 10px 6px; white-space: nowrap; }
th.num, td.num { text-align: right; }
th button { font: inherit; color: inherit; background: none; border: 0; padding: 0;
  cursor: pointer; }
th[aria-sort] button { color: var(--ink); }
th[aria-sort=ascending] button::after { content: " \25B2"; font-size: 9px; }
th[aria-sort=descending] button::after { content: " \25BC"; font-size: 9px; }
td { padding: 7px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
tbody tr:hover { background: var(--row); }
td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
td.name button { font: inherit; font-weight: 600; color: var(--ink); background: none;
  border: 0; padding: 0; cursor: copy; text-align: left; }
td.name small { display: block; color: var(--muted);
  font: 11.5px ui-monospace, Menlo, monospace; word-break: break-all; }
td.tris { min-width: 190px; }
.bar { height: 4px; border-radius: 2px; background: var(--bar); margin: 4px 0 0 auto;
  min-width: 1px; }
td small.cat { display: block; color: var(--muted); font-size: 11.5px; }
.tag { font-size: 11px; border-radius: 4px; padding: 1px 6px; margin-left: 6px;
  background: var(--nanite-soft); color: var(--nanite); font-weight: 600; }
.tag.bones { background: var(--accent-soft); color: var(--accent); }
.dim { color: var(--muted); }
.empty { padding: 40px 0; color: var(--muted); text-align: center; }
td.pic { width: 76px; padding: 4px 4px 4px 10px; }
td.pic img, td.pic div { display: block; width: 64px; height: 64px; border-radius: 6px;
  background: var(--row); }
td.pic img { object-fit: contain; }
td.pic button { display: block; padding: 0; border: 0; background: none; border-radius: 6px;
  cursor: zoom-in; }
td.pic button:focus-visible, #viewClose:focus-visible { outline: 2px solid var(--accent);
  outline-offset: 2px; }
#view { width: min(92vw, 640px, calc(100vh - 150px)); padding: 16px; color: var(--ink);
  background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, .4); }
#view::backdrop { background: rgba(0, 0, 0, .55); }
#stage { position: relative; width: 100%; aspect-ratio: 1; overflow: hidden;
  background: var(--row); border-radius: 8px; touch-action: none; user-select: none; }
#stage.turns { cursor: grab; }
#stage.turns:active { cursor: grabbing; }
#stage img, #viewSpin { position: absolute; inset: 0; width: 100%; height: 100%; }
#stage img { object-fit: contain; }
#viewSpin { background-repeat: no-repeat; }
.cap { display: flex; gap: 12px; align-items: baseline; margin-top: 12px; padding-right: 0; }
.cap b { font-weight: 650; word-break: break-all; }
.cap span, .hint { color: var(--muted); font-size: 12.5px; }
.cap span { margin-left: auto; white-space: nowrap; font-variant-numeric: tabular-nums; }
#viewClose { position: absolute; top: 22px; right: 22px; width: 30px; height: 30px;
  font: 18px/1 inherit; color: var(--ink); background: var(--panel);
  border: 1px solid var(--line); border-radius: 50%; cursor: pointer; }
#big { position: fixed; z-index: 3; width: 280px; height: 280px; padding: 12px;
  background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, .28); pointer-events: none; }
#big img { width: 100%; height: 100%; object-fit: contain; }
#toast { position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%);
  background: var(--ink); color: var(--bg); padding: 7px 14px; border-radius: 6px;
  font-size: 13px; opacity: 0; transition: opacity .15s; pointer-events: none; }
#toast.on { opacity: 1; }
</style>
</head>
<body>
<header>
  <h1>Otherworld assets</h1>
  <div class="sub">Every static and skeletal mesh under <code>/Game</code>, scanned <span id="scanned"></span>.
    Rebuild: <code>python3 Scripts/build_map_asset_browser.py --open</code></div>
  <div class="stats" id="stats"></div>
</header>
<div class="controls">
  <div class="tabs" id="cats" role="tablist" aria-label="Category"></div>
  <input type="search" id="q" placeholder="Search name or path" aria-label="Search name or path">
  <select id="pack" aria-label="Pack"></select>
  <label class="check"><input type="checkbox" id="usedOnly"> Used by a level</label>
  <label class="check"><input type="checkbox" id="naniteOnly"> Nanite</label>
  <div class="chips" id="kinds"></div>
</div>
<div class="wrap">
  <table>
    <thead><tr id="head"></tr></thead>
    <tbody id="rows"></tbody>
  </table>
  <div class="empty" id="empty" hidden>No mesh matches these filters.</div>
</div>
<div id="big" hidden><img alt=""></div>
<dialog id="view" aria-labelledby="viewName">
  <div id="stage"><img id="viewStill" alt="" draggable="false"><div id="viewSpin" hidden></div></div>
  <div class="cap"><b id="viewName"></b><span id="viewMeta"></span></div>
  <div class="hint" id="viewHint"></div>
  <button id="viewClose" aria-label="Close">&times;</button>
</dialog>
<div id="toast" role="status">Path copied</div>
<script id="scan" type="application/json">__SCAN__</script>
<script>
const scan = JSON.parse(document.getElementById("scan").textContent);
const meshes = scan.meshes;
const COLS = [
  ["name", "Mesh", false, "Click a name to copy its /Game path"],
  ["pack", "Pack", false, ""],
  ["kind", "Kind", false, "Category and kind, guessed from the path"],
  ["triangles", "Triangles", true, "What the mesh is built from: the Nanite count on a Nanite mesh, LOD 0 otherwise"],
  ["lod0_triangles", "LOD 0", true, "Triangles drawn without Nanite. On a Nanite mesh this is the fallback"],
  ["vertices", "Vertices", true, "LOD 0"],
  ["lods", "LODs", true, ""],
  ["materials", "Materials", true, "Material slots"],
  ["size", "Size, cm", false, "Approximate bounds"],
  ["levels", "Levels", false, "Levels that reference the mesh"],
];
const state = { sort: "triangles", dir: -1, kinds: new Set(), category: "" };
const $ = id => document.getElementById(id);
const dash = '<span class="dim" title="Not recorded for a skeletal mesh">–</span>';
const fmt = n => n.toLocaleString("en-US");
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));

function sortKey(m, col) {
  if (col === "size") return m.size_cm.split("x").reduce((a, b) => a * (parseFloat(b) || 0), 1);
  if (col === "levels") return m.levels.length;
  if (col === "kind") return scan.categories.indexOf(m.category) + " " + m.kind;
  const v = m[col];
  return typeof v === "string" ? v.toLowerCase() : v;
}

function visible(ignoreKinds, ignoreCategory) {
  const q = $("q").value.trim().toLowerCase(), pack = $("pack").value;
  return meshes.filter(m =>
    (ignoreCategory || !state.category || m.category === state.category) &&
    (!$("usedOnly").checked || m.levels.length) &&
    (!$("naniteOnly").checked || m.nanite) &&
    (!pack || m.pack === pack) &&
    (!q || m.path.toLowerCase().includes(q)) &&
    (ignoreKinds || !state.kinds.size || state.kinds.has(m.kind)));
}

function renderHead() {
  $("head").innerHTML = "<th></th>" + COLS.map(([key, label, num, tip]) => {
    const sorted = state.sort === key ? ` aria-sort="${state.dir > 0 ? "ascending" : "descending"}"` : "";
    return `<th class="${num ? "num" : ""}"${sorted} title="${esc(tip)}"><button data-col="${key}">${label}</button></th>`;
  }).join("");
}

function renderCats() {
  const counts = {};
  const all = visible(true, true);
  for (const m of all) counts[m.category] = (counts[m.category] || 0) + 1;
  const tabs = [["", "All", all.length]].concat(
    scan.categories.filter(c => counts[c] || c === state.category).map(c => [c, c, counts[c] || 0]));
  $("cats").innerHTML = tabs.map(([key, label, n]) =>
    `<button class="tab" role="tab" data-cat="${key}" aria-selected="${state.category === key}">${label}<i>${n}</i></button>`).join("");
}

function renderKinds() {
  const counts = {};
  for (const m of visible(true)) counts[m.kind] = (counts[m.kind] || 0) + 1;
  for (const k of [...state.kinds]) if (!counts[k]) state.kinds.delete(k);
  $("kinds").innerHTML = Object.keys(counts).sort().map(k =>
    `<button class="chip" data-kind="${k}" aria-pressed="${state.kinds.has(k)}">${k}<i>${counts[k]}</i></button>`).join("");
}

function renderStats(rows) {
  const total = rows.reduce((a, m) => a + m.triangles, 0);
  const heavy = rows.reduce((a, m) => (!a || m.triangles > a.triangles ? m : a), null);
  const tris = rows.map(m => m.triangles).sort((a, b) => a - b);
  const median = tris.length ? tris[Math.floor(tris.length / 2)] : 0;
  const cells = [
    [fmt(rows.length), `meshes shown, of ${fmt(meshes.length)} in the project`],
    [fmt(total), "triangles, one of each"],
    [fmt(median), "median triangles"],
    [heavy ? fmt(heavy.triangles) : "0", heavy ? `heaviest: ${esc(heavy.name)}` : "heaviest"],
    [fmt(rows.filter(m => m.nanite).length), "Nanite meshes"],
  ];
  $("stats").innerHTML = cells.map(([b, s]) => `<div class="stat"><b>${b}</b><span>${s}</span></div>`).join("");
}

function render() {
  renderCats();
  renderKinds();
  const rows = visible(false);
  const col = state.sort;
  rows.sort((a, b) => {
    const x = sortKey(a, col), y = sortKey(b, col);
    return (x < y ? -1 : x > y ? 1 : a.path < b.path ? -1 : 1) * (x === y ? 1 : state.dir);
  });
  const max = rows.reduce((a, m) => Math.max(a, m.triangles), 1);
  $("rows").innerHTML = rows.map(m => `<tr>
    <td class="pic">${m.thumb ? `<button data-open="${esc(m.path)}" title="Enlarge${m.spin ? " and turn" : ""}"><img loading="lazy" src="${esc(m.thumb)}" alt="${esc(m.name)}"></button>` : "<div></div>"}</td>
    <td class="name"><button data-path="${esc(m.path)}" title="Copy path">${esc(m.name)}</button>${m.nanite ? '<span class="tag">Nanite</span>' : ""}${m.type === "skeletal" ? `<span class="tag bones" title="Skeletal mesh">${m.bones} bones</span>` : ""}<small>${esc(m.path)}</small></td>
    <td>${esc(m.pack)}</td>
    <td>${m.kind}<small class="cat">${m.category}</small></td>
    <td class="num tris">${fmt(m.triangles)}<div class="bar" style="width:${(100 * m.triangles / max).toFixed(2)}%"></div></td>
    <td class="num${m.nanite ? "" : " dim"}">${fmt(m.lod0_triangles)}</td>
    <td class="num">${m.vertices ? fmt(m.vertices) : dash}</td>
    <td class="num">${m.lods || dash}</td>
    <td class="num">${m.materials || dash}</td>
    <td class="num">${m.size_cm ? esc(m.size_cm.replace(/x/g, " × ")) : dash}</td>
    <td>${m.levels.length ? esc(m.levels.join(", ")) : '<span class="dim">none</span>'}</td>
  </tr>`).join("");
  $("empty").hidden = rows.length > 0;
  renderStats(rows);
  renderHead();
}

function fillPacks() {
  const counts = {};
  for (const m of meshes) if (!state.category || m.category === state.category) counts[m.pack] = (counts[m.pack] || 0) + 1;
  const kept = $("pack").value;
  $("pack").innerHTML = `<option value="">All packs</option>` + Object.keys(counts).sort().map(p =>
    `<option value="${esc(p)}">${esc(p)} (${counts[p]})</option>`).join("");
  $("pack").value = counts[kept] ? kept : "";
}

$("scanned").textContent = scan.scanned;
$("head").addEventListener("click", e => {
  const col = e.target.dataset.col;
  if (!col) return;
  const text = ["name", "pack", "kind"].includes(col);
  state.dir = state.sort === col ? -state.dir : (text ? 1 : -1);
  state.sort = col;
  render();
});
$("kinds").addEventListener("click", e => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  const k = chip.dataset.kind;
  state.kinds.has(k) ? state.kinds.delete(k) : state.kinds.add(k);
  render();
});
$("rows").addEventListener("mouseover", e => {
  if (e.target.tagName !== "IMG") return;
  const box = e.target.getBoundingClientRect(), big = $("big");
  big.firstChild.src = e.target.src;
  big.style.left = (box.right + 12) + "px";
  big.style.top = Math.max(8, Math.min(box.top - 100, innerHeight - 290)) + "px";
  big.hidden = false;
});
$("rows").addEventListener("mouseout", e => { if (e.target.tagName === "IMG") $("big").hidden = true; });
// The large view. A turn is a strip of scan.spin_frames frames; a frame is
// shown by sliding the strip, so a drag never waits for a file.
const byPath = new Map(meshes.map(m => [m.path, m]));
const view = { path: "", frame: 0, turns: false, drag: null };

function showFrame(frame) {
  const n = scan.spin_frames;
  view.frame = ((frame % n) + n) % n;
  $("viewSpin").style.backgroundPosition = `${100 * view.frame / (n - 1)}% 0`;
}

function openView(m) {
  const still = $("viewStill"), spin = $("viewSpin");
  $("big").hidden = true;
  view.path = m.path;
  view.turns = false;
  view.drag = null;
  $("stage").classList.remove("turns");
  $("viewName").textContent = m.name;
  $("viewMeta").textContent = `${fmt(m.triangles)} triangles · ${m.kind}`;
  $("viewHint").textContent = m.spin ? "Loading the turn…" : "This mesh has no turn: run the build again to shoot one.";
  still.src = m.thumb;
  still.alt = m.name;
  still.hidden = false;
  spin.hidden = true;
  if (m.spin) {
    const strip = new Image();
    strip.onload = () => {
      if (view.path !== m.path) return;
      spin.style.backgroundImage = `url("${m.spin}")`;
      spin.style.backgroundSize = `${scan.spin_frames * 100}% 100%`;
      showFrame(0);
      spin.hidden = false;
      still.hidden = true;
      view.turns = true;
      $("stage").classList.add("turns");
      $("viewHint").textContent = "Drag sideways, or press ← and →, to turn it. Esc closes.";
    };
    strip.onerror = () => { if (view.path === m.path) $("viewHint").textContent = "The turn's file is missing: " + m.spin; };
    strip.src = m.spin;
  }
  $("view").showModal();
}

$("stage").addEventListener("pointerdown", e => {
  if (!view.turns) return;
  $("stage").setPointerCapture(e.pointerId);
  view.drag = { x: e.clientX, frame: view.frame };
});
$("stage").addEventListener("pointermove", e => {
  if (!view.drag) return;
  // One width of the stage is one whole turn; the near side follows the pointer.
  const step = $("stage").clientWidth / scan.spin_frames;
  showFrame(view.drag.frame + Math.round((e.clientX - view.drag.x) / step));
});
for (const type of ["pointerup", "pointercancel"]) $("stage").addEventListener(type, () => { view.drag = null; });
$("view").addEventListener("keydown", e => {
  if (!view.turns || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
  e.preventDefault();
  showFrame(view.frame + (e.key === "ArrowRight" ? 1 : -1));
});
$("view").addEventListener("click", e => {
  const box = $("view").getBoundingClientRect();
  const outside = e.clientX < box.left || e.clientX > box.right || e.clientY < box.top || e.clientY > box.bottom;
  if (e.target === $("viewClose") || (e.target === $("view") && outside)) $("view").close();
});
$("rows").addEventListener("click", e => {
  const opener = e.target.closest("[data-open]");
  if (opener) return openView(byPath.get(opener.dataset.open));
  const path = e.target.dataset.path;
  if (!path || !navigator.clipboard) return;
  navigator.clipboard.writeText(path).then(() => {
    $("toast").classList.add("on");
    setTimeout(() => $("toast").classList.remove("on"), 1100);
  });
});
$("cats").addEventListener("click", e => {
  const tab = e.target.closest(".tab");
  if (!tab) return;
  state.category = tab.dataset.cat;
  state.kinds.clear();
  fillPacks();
  render();
});
for (const id of ["q", "pack", "usedOnly", "naniteOnly"]) $(id).addEventListener("input", render);
fillPacks();
render();
</script>
</body>
</html>
"""


def render(scan, thumbs=None, spins=None):
    """The page's HTML for a scan ({"scanned": ..., "meshes": [...]}). Each
    mesh is given its pack, its category, its kind, its picture and its turn."""
    folder, spin_folder = os.path.basename(THUMB_DIR), os.path.basename(SPIN_DIR)
    scan["categories"] = list(CATEGORIES)
    scan["spin_frames"] = SPIN_FRAMES
    for mesh in scan["meshes"]:
        mesh["pack"] = pack_of(mesh["path"])
        mesh["category"], mesh["kind"] = classify(mesh["path"])
        mesh.setdefault("type", "static")
        mesh.setdefault("bones", 0)
        name = (thumbs or {}).get(mesh["path"])
        mesh["thumb"] = f"{folder}/{name}" if name else ""
        name = (spins or {}).get(mesh["path"])
        mesh["spin"] = f"{spin_folder}/{name}" if name else ""
    # "</" would end the script element the JSON sits in.
    data = json.dumps(scan, separators=(",", ":")).replace("</", "<\\/")
    return TEMPLATE.replace("__SCAN__", data)


def build(thumbs=None, spins=None):
    """Write PAGE_HTML from SCAN_JSON. Returns (path, {category: meshes})."""
    with open(SCAN_JSON) as fh:
        scan = json.load(fh)
    with open(PAGE_HTML, "w") as fh:
        fh.write(render(scan, thumbs, spins))
    counts = {c: sum(m["category"] == c for m in scan["meshes"]) for c in CATEGORIES}
    return PAGE_HTML, {c: n for c, n in counts.items() if n}
