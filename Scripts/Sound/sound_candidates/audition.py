"""The audition page: every sound on one HTML page, a button each.

Lists the candidates (`assets/generated/sound_candidates/`) by category, and
the sounds the game plays now (`assets/generated/sounds/`) as a last category
to compare against. The page sits beside both folders and links the WAVs by
relative path, so it opens straight from disk: no server.

A take can be rated, RATINGS below. The ratings are kept in the browser, and
the page lists them as text to copy: that list is how the verdicts get back to
whoever wires the sounds in.
"""

import html
import json
import os
import urllib.parse
import wave

from sound_candidates import audition_selected

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
GENERATED_DIR = os.path.join(_PROJECT_DIR, "assets", "generated")
PAGE_PATH = os.path.join(GENERATED_DIR, "sound_audition.html")

# (folder under assets/generated, heading prefix). The game's own set is one
# flat folder, so it is one category.
CANDIDATES = "sound_candidates"
CURRENT = "sounds"
CURRENT_HEADING = "in the game now"

# (key, label, button text, keyboard digit), best first. A take with no rating
# has not been judged, which is not the same as neutral.
RATINGS = (
    ("great", "Great", "++", "5"),
    ("ok", "Ok", "+", "4"),
    ("neutral", "Neutral", "\u25cb", "3"),
    ("bad", "Bad", "\u2212", "2"),
    ("verybad", "Very bad", "\u2212\u2212", "1"),
    # Not a point on the scale: the sound is good and the category is wrong.
    # It carries a note saying what it would be good for.
    ("reuse", "Good, other use", "\u21aa", "6"),
)
# The ratings that show the note box: a take that was liked can say why, or
# what for. NOTE_FIRST is the one whose click puts the cursor in the box,
# because its note is the point of it; on the others the box is only there.
NOTED = ("great", "ok", "reuse")
NOTE_FIRST = "reuse"

# Beds are judged looping; everything else is a one-shot.
LOOPED = ("ambience", "fire")


def _wave_info(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate()), w.getnchannels()


def _stem(name):
    """`grass_walk_03` -> `grass_walk`: the sound a numbered take belongs to."""
    head, _, tail = name.rpartition("_")
    return head if head and tail.isdigit() else name


def collect():
    """`[(category, [(sound, [take])])]`, where a take is a dict the page
    renders. Categories and sounds are in name order, the game's own last."""
    groups = {}
    root = os.path.join(GENERATED_DIR, CANDIDATES)
    for folder, _dirs, files in os.walk(root):
        for name in sorted(files):
            if name.endswith(".wav"):
                category = os.path.relpath(folder, root).replace(os.sep, " / ")
                _add(groups, category, os.path.join(folder, name))
    current = os.path.join(GENERATED_DIR, CURRENT)
    if os.path.isdir(current):
        for name in sorted(os.listdir(current)):
            if name.endswith(".wav"):
                _add(groups, CURRENT_HEADING, os.path.join(current, name))

    order = sorted(c for c in groups if c != CURRENT_HEADING)
    if CURRENT_HEADING in groups:
        order.append(CURRENT_HEADING)
    return [(c, sorted(groups[c].items())) for c in order]


def _add(groups, category, path):
    seconds, channels = _wave_info(path)
    name = os.path.splitext(os.path.basename(path))[0]
    rel = os.path.relpath(path, GENERATED_DIR).replace(os.sep, "/")
    take = dict(id=os.path.splitext(rel)[0], name=name, seconds=seconds,
                channels=channels, src=urllib.parse.quote(rel))
    groups.setdefault(category, {}).setdefault(_stem(name), []).append(take)


_STYLE = """
:root { --bg:#f6f5f1; --panel:#fff; --ink:#1d1d1b; --dim:#6b6a65; --line:#dedcd4;
        --accent:#2f6f4f; --accent-ink:#fff; color-scheme: light;
        --great:#1f8a4c; --ok:#6aa84f; --neutral:#8a8983; --bad:#d9822b; --verybad:#c0392b;
        --reuse:#3b6fd4; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#161715; --panel:#1f211e; --ink:#e9e7e0; --dim:#9a988f; --line:#33352f;
          --accent:#6fbf93; --accent-ink:#10140f; color-scheme: dark;
          --great:#4fc47f; --ok:#9bcf7c; --neutral:#a3a199; --bad:#f0a04b; --verybad:#ef6a5b;
          --reuse:#7da6f5; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font:14px/1.45 -apple-system, "Segoe UI", system-ui, sans-serif; }
header { position:sticky; top:0; z-index:2; background:var(--bg);
         border-bottom:1px solid var(--line); padding:12px 20px; }
header h1 { font-size:16px; margin:0 0 8px; }
.bar { display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center; }
.bar input[type=search] { flex:1 1 220px; max-width:340px; padding:6px 10px;
       border:1px solid var(--line); border-radius:6px; background:var(--panel); color:var(--ink); }
.bar label { color:var(--dim); display:flex; gap:6px; align-items:center; }
.bar select { font:inherit; padding:5px 8px; border:1px solid var(--line); border-radius:6px;
       background:var(--panel); color:var(--ink); }
.hint { color:var(--dim); font-size:12px; margin-top:8px; }
kbd { font:11px ui-monospace, Menlo, monospace; border:1px solid var(--line);
      border-radius:4px; padding:0 4px; background:var(--panel); }
nav { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
nav a { color:var(--dim); text-decoration:none; padding:2px 8px;
        border:1px solid var(--line); border-radius:999px; font-size:12px; }
nav a:hover { color:var(--ink); border-color:var(--dim); }
#now { color:var(--dim); font-variant-numeric:tabular-nums; min-height:1.45em; }
main { padding:8px 20px 60px; max-width:1100px; }
section { margin-top:22px; scroll-margin-top:130px; }
section h2 { font-size:13px; text-transform:uppercase; letter-spacing:.08em;
             color:var(--dim); margin:0 0 8px; }
.sound { display:grid; grid-template-columns:minmax(120px,200px) 1fr; gap:6px 14px;
         padding:8px 12px; background:var(--panel); border:1px solid var(--line);
         border-radius:8px; margin-bottom:6px; align-items:start; }
.sound .label { padding-top:5px; overflow-wrap:anywhere; font-weight:600; }
.takes { display:flex; flex-wrap:wrap; gap:6px; }
.take { display:inline-flex; border:1px solid var(--line); border-radius:6px; overflow:hidden; }
.take button { font:inherit; border:0; background:transparent; color:var(--ink);
               padding:5px 9px; cursor:pointer; font-variant-numeric:tabular-nums; }
.take .play { min-width:74px; text-align:left; }
.take .play small { color:var(--dim); margin-left:6px; }
.take .play:hover { background:color-mix(in srgb, var(--accent) 14%, transparent); }
.take.playing .play { background:var(--accent); color:var(--accent-ink); }
.take.playing .play small { color:inherit; }
.take.focus { outline:2px solid var(--accent); outline-offset:1px; }
.rate { display:inline-flex; border-left:1px solid var(--line); }
.rate button { padding:5px 6px; min-width:24px; color:var(--dim); font-size:12px; opacity:.55; }
.rate button:hover { opacity:1; color:var(--c); }
.rate button[data-r=great], .take[data-rating=great] { --c:var(--great); }
.rate button[data-r=ok], .take[data-rating=ok] { --c:var(--ok); }
.rate button[data-r=neutral], .take[data-rating=neutral] { --c:var(--neutral); }
.rate button[data-r=bad], .take[data-rating=bad] { --c:var(--bad); }
.rate button[data-r=verybad], .take[data-rating=verybad] { --c:var(--verybad); }
.rate button[data-r=reuse], .take[data-rating=reuse] { --c:var(--reuse); }
.rate button[data-r=reuse] { border-left:1px solid var(--line); }
.take .note { display:none; font:inherit; font-size:12px; width:150px; padding:4px 7px; border:0;
       border-left:1px solid var(--line); background:transparent; color:var(--ink); }
.take[data-rating=great] .note, .take[data-rating=ok] .note,
.take[data-rating=reuse] .note { display:block; }
.take[data-rating] { border-color:var(--c); box-shadow:inset 3px 0 0 var(--c); }
.rate button.on { opacity:1; background:var(--c); color:#fff; font-weight:700; }
#picks { margin-top:28px; }
#picks textarea { width:100%; min-height:220px; padding:10px; border-radius:8px;
       border:1px solid var(--line); background:var(--panel); color:var(--ink);
       font:12px/1.5 ui-monospace, Menlo, monospace; }
#picks button { font:inherit; margin-top:6px; padding:5px 12px; border-radius:6px;
       border:1px solid var(--line); background:var(--panel); color:var(--ink); cursor:pointer; }
[hidden] { display:none !important; }
@media (max-width:560px) { .sound { grid-template-columns:1fr; } }
"""

_SCRIPT = """
const player = new Audio();
const now = document.getElementById('now');
const loopBox = document.getElementById('loop');
const volume = document.getElementById('volume');
let current = null;

function stop() {
  player.pause();
  if (current) current.classList.remove('playing');
  current = null;
  now.textContent = '';
}
// The take the number keys rate: the last one played, playing or not.
let focused = null;
function focus(take) {
  if (focused) focused.classList.remove('focus');
  focused = take;
  take.classList.add('focus');
}
function play(take) {
  const same = take === current;
  stop();
  focus(take);
  if (same) return;
  current = take;
  take.classList.add('playing');
  player.src = take.dataset.src;
  player.loop = loopBox.checked && take.dataset.loop === '1';
  player.volume = volume.value;
  player.currentTime = 0;
  player.play();
  now.textContent = 'playing ' + take.dataset.id + (player.loop ? ' (looping)' : '');
}
player.addEventListener('ended', stop);
volume.addEventListener('input', () => { player.volume = volume.value; });
document.addEventListener('keydown', e => {
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.code === 'Space') { e.preventDefault(); stop(); return; }
  if (!focused || !focused.classList.contains('take')) return;   // a pick is not rated
  if (e.key === '0') { rate(focused, null); return; }
  const hit = RATINGS.find(r => r.digit === e.key);
  if (hit) rate(focused, hit.key);
});

// The two tabs: every sound, and the selection.
const VIEW_KEY = 'otherworld-sound-view';
function show(view) {
  document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('on', b.dataset.view === view));
  document.querySelectorAll('[data-in]').forEach(el => { el.hidden = el.dataset.in !== view; });
  try { localStorage.setItem(VIEW_KEY, view); } catch (e) {}
}
document.querySelectorAll('.tabs button').forEach(b => b.addEventListener('click', () => show(b.dataset.view)));
let view = 'all';
try { view = localStorage.getItem(VIEW_KEY) || 'all'; } catch (e) {}
show(view === 'selected' ? 'selected' : 'all');
document.querySelectorAll('button.pick').forEach(p => p.addEventListener('click', () => play(p)));

// Ratings live in this browser only; the textarea is how they leave it.
const KEY = 'otherworld-sound-ratings';
let ratings = {};
try { ratings = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
try {   // the stars this page had before it had ratings
  for (const id of JSON.parse(localStorage.getItem('otherworld-sound-picks') || '[]')) {
    if (!(id in ratings)) ratings[id] = 'great';
  }
} catch (e) {}
// A liked take's note, by take id: why, or what for. Kept when the rating
// changes, so a note is not lost to a slip of the finger.
const NOTES_KEY = 'otherworld-sound-notes';
let notes = {};
try { notes = JSON.parse(localStorage.getItem(NOTES_KEY) || '{}'); } catch (e) {}
const takes = [...document.querySelectorAll('.take')];
const ratedBox = document.getElementById('rated');

function paint(take) {
  const r = ratings[take.dataset.id];
  if (r) take.dataset.rating = r; else delete take.dataset.rating;
  take.querySelectorAll('.rate button').forEach(b => b.classList.toggle('on', b.dataset.r === r));
}
function rate(take, r) {
  const id = take.dataset.id;
  if (!r || ratings[id] === r) delete ratings[id]; else ratings[id] = r;
  paint(take);
  report();
}
function report() {
  const lines = [];
  let rated = 0;
  for (const {key, label} of RATINGS) {
    const ids = takes.map(t => t.dataset.id).filter(id => ratings[id] === key);
    rated += ids.length;
    const line = id => '  ' + id + (NOTED.includes(key) && notes[id] ? '  -- ' + notes[id] : '');
    if (ids.length) lines.push(label + ' (' + ids.length + ')', ...ids.map(line), '');
  }
  ratedBox.value = lines.join('\\n').trimEnd();
  document.getElementById('ratedcount').textContent = rated + ' of ' + takes.length;
  try {
    localStorage.setItem(KEY, JSON.stringify(ratings));
    localStorage.setItem(NOTES_KEY, JSON.stringify(notes));
  } catch (e) {}
  applyFilter();
}
takes.forEach(take => {
  paint(take);
  take.querySelector('.play').addEventListener('click', () => play(take));
  take.querySelectorAll('.rate button').forEach(b =>
    b.addEventListener('click', () => {
      focus(take);
      rate(take, b.dataset.r);
      if (b.dataset.r === NOTE_FIRST && ratings[take.dataset.id] === NOTE_FIRST) note.focus();
    }));
  const note = take.querySelector('.note');
  note.value = notes[take.dataset.id] || '';
  note.addEventListener('input', () => {
    const text = note.value.trim();
    if (text) notes[take.dataset.id] = text; else delete notes[take.dataset.id];
    report();
  });
});
document.getElementById('clear').addEventListener('click', () => {
  const box = document.getElementById('confirm');
  box.hidden = !box.hidden;
});
document.getElementById('clear-yes').addEventListener('click', () => {
  ratings = {};
  notes = {};
  takes.forEach(t => { paint(t); t.querySelector('.note').value = ''; });
  document.getElementById('confirm').hidden = true;
  report();
});
document.getElementById('copy').addEventListener('click', () => {
  ratedBox.select();
  navigator.clipboard && navigator.clipboard.writeText(ratedBox.value);
});

// One filter, two inputs: the text and the rating.
const filterBox = document.getElementById('filter');
const showBox = document.getElementById('show');
function applyFilter() {
  const q = filterBox.value.trim().toLowerCase();
  const show = showBox.value;
  document.querySelectorAll('section.category').forEach(section => {
    let any = false;
    section.querySelectorAll('.sound').forEach(sound => {
      let hit = false;
      if (!q || sound.dataset.search.includes(q)) {
        sound.querySelectorAll('.take').forEach(take => {
          const r = ratings[take.dataset.id];
          const keep = show === 'all' || (show === 'unrated' ? !r : r === show);
          take.hidden = !keep;
          hit = hit || keep;
        });
      }
      sound.hidden = !hit;
      any = any || hit;
    });
    section.hidden = !any;
  });
}
filterBox.addEventListener('input', applyFilter);
showBox.addEventListener('change', applyFilter);
report();
"""


def _anchor(category):
    return "c-" + "".join(ch if ch.isalnum() else "-" for ch in category)


def _take_html(take, looped):
    e = html.escape
    stereo = " st" if take["channels"] == 2 else ""
    return (
        f'<span class="take" data-id="{e(take["id"])}" data-src="{e(take["src"])}"'
        f' data-loop="{1 if looped else 0}">'
        f'<button class="play" title="{e(take["name"])}">&#9654; {e(_take_label(take))}'
        f'<small>{take["seconds"]:.1f}s{stereo}</small></button>'
        f'<span class="rate">{_RATE_BUTTONS}</span>'
        f'<input class="note" type="text" placeholder="note\u2026" '
        f'title="A note on this take: why it is good, or what for"></span>')


_RATE_BUTTONS = "".join(
    f'<button data-r="{key}" title="{label} ({digit})">{text}</button>'
    for key, label, text, digit in RATINGS)


def _take_label(take):
    tail = take["name"].rpartition("_")[2]
    return tail if tail.isdigit() else "play"


def render(groups):
    e = html.escape
    total = sum(len(takes) for _c, sounds in groups for _s, takes in sounds)
    selected_html, selected_count = audition_selected.render()
    nav, body = [], []
    for category, sounds in groups:
        count = sum(len(takes) for _s, takes in sounds)
        looped = category.split(" / ")[0] in LOOPED
        nav.append(f'<a href="#{_anchor(category)}">{e(category)} {count}</a>')
        rows = []
        for sound, takes in sounds:
            search = e(f"{category} {sound}".lower())
            buttons = "".join(_take_html(t, looped) for t in takes)
            rows.append(f'<div class="sound" data-search="{search}">'
                        f'<div class="label">{e(sound)}</div>'
                        f'<div class="takes">{buttons}</div></div>')
        body.append(f'<section class="category" id="{_anchor(category)}">'
                    f'<h2>{e(category)} &middot; {count}</h2>{"".join(rows)}</section>')

    options = "".join(f'<option value="{key}">{e(label.lower())}</option>'
                      for key, label, _text, _digit in RATINGS)
    ratings_js = json.dumps([dict(key=key, label=label, digit=digit)
                             for key, label, _text, digit in RATINGS])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Otherworld sound audition</title>
<style>{_STYLE}{audition_selected.STYLE}</style></head><body>
<header>
  <h1>Otherworld sound audition
    <span class="tabs"><button data-view="all">All sounds &middot; {total}</button><button
      data-view="selected">Selected &middot; {selected_count}</button></span></h1>
  <div class="bar">
    <input type="search" id="filter" placeholder="Filter by name or category">
    <label>Volume <input type="range" id="volume" min="0" max="1" step="0.05" value="0.8"></label>
    <label>Show <select id="show"><option value="all">all</option>
      <option value="unrated">unrated</option>{options}</select></label>
    <label><input type="checkbox" id="loop" checked> Loop ambience and fire</label>
    <span id="now"></span>
  </div>
  <nav data-in="all">{"".join(nav)}<a href="#picks">ratings</a></nav>
  <div class="hint" data-in="all">Rate the last take played with <kbd>5</kbd> great, <kbd>4</kbd> ok,
    <kbd>3</kbd> neutral, <kbd>2</kbd> bad, <kbd>1</kbd> very bad, <kbd>6</kbd> good but for another use. A take rated great, ok or other-use has a note box, <kbd>0</kbd> clear.
    <kbd>Space</kbd> stops.</div>
</header>
<main data-in="selected">{selected_html}</main>
<main data-in="all">
{"".join(body)}
<section id="picks">
  <h2>Ratings &middot; <span id="ratedcount">0</span> rated</h2>
  <textarea id="rated" readonly></textarea>
  <button id="copy">Copy</button> <button id="clear">Clear all ratings</button>
  <span id="confirm" hidden>Clear every rating? <button id="clear-yes">Yes, clear</button></span>
</section>
</main>
<script>const RATINGS = {ratings_js};
const NOTED = {json.dumps(NOTED)};
const NOTE_FIRST = {json.dumps(NOTE_FIRST)};
{_SCRIPT}</script>
</body></html>
"""


def build():
    """Write the page. Returns `(path, number of sounds)`."""
    groups = collect()
    with open(PAGE_PATH, "w", encoding="utf-8") as out:
        out.write(render(groups))
    return PAGE_PATH, sum(len(t) for _c, sounds in groups for _s, t in sounds)
