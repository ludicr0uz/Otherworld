"""The audition page's second tab: the selection, use by use.

One section per category of `selection.py`, one row per use: what it is for,
where it stands (in the game, ready, for later), and its sounds as buttons. A
use the game plays shows the installed sounds themselves
(`assets/generated/sounds/`), so a reload put together from three takes is
heard as the one sound the game has; the others show the chosen takes.
"""

import html
import os
import urllib.parse
import wave

from sound_candidates import selection
from sound_candidates.selection import FUTURE, GAME, READY

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
GENERATED_DIR = os.path.join(_PROJECT_DIR, "assets", "generated")
LOOPED = ("ambience", "fire")
BADGE = {GAME: "game", READY: "ready", FUTURE: "later"}

STYLE = """
.tabs { display:inline-flex; border:1px solid var(--line); border-radius:8px; overflow:hidden; margin-left:14px;
        vertical-align:middle; }
.tabs button { font:inherit; font-weight:600; border:0; background:transparent; color:var(--dim);
        padding:5px 14px; cursor:pointer; }
.tabs button.on { background:var(--accent); color:var(--accent-ink); }
.use { display:grid; grid-template-columns:minmax(160px,280px) 1fr; gap:6px 14px; padding:9px 12px;
       background:var(--panel); border:1px solid var(--line); border-radius:8px; margin-bottom:6px; }
.use .what { font-weight:600; overflow-wrap:anywhere; }
.use .note { display:block; font-weight:400; color:var(--dim); font-size:12px; margin-top:3px; }
.badge { display:inline-block; font-size:11px; font-weight:600; padding:0 7px; border-radius:999px;
         margin-left:6px; border:1px solid var(--line); color:var(--dim); vertical-align:1px; }
.badge.game { border-color:var(--great); color:var(--great); }
.badge.later { border-color:var(--reuse); color:var(--reuse); }
.picks { display:flex; flex-wrap:wrap; gap:6px; align-content:flex-start; }
.pick { font:inherit; border:1px solid var(--line); border-radius:6px; background:transparent;
        color:var(--ink); padding:5px 9px; cursor:pointer; font-variant-numeric:tabular-nums; }
.pick small { color:var(--dim); margin-left:6px; }
.pick:hover { background:color-mix(in srgb, var(--accent) 14%, transparent); }
.pick.playing { background:var(--accent); color:var(--accent-ink); border-color:var(--accent); }
.pick.playing small { color:inherit; }
.pick.missing { opacity:.45; cursor:default; text-decoration:line-through; }
.legend { color:var(--dim); font-size:12px; margin:14px 0 0; }
@media (max-width:560px) { .use { grid-template-columns:1fr; } }
"""


def _seconds(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())


def _button(rel, label, title, looped):
    """A play button for `rel`, a path under assets/generated without `.wav`."""
    e = html.escape
    path = os.path.join(GENERATED_DIR, rel + ".wav")
    if not os.path.isfile(path):
        return f'<span class="pick missing" title="{e(title)}: no file">{e(label)}</span>'
    return (f'<button class="pick" data-id="{e(rel)}" data-src="{e(urllib.parse.quote(rel + ".wav"))}" '
            f'data-loop="{1 if looped else 0}" title="{e(title)}">&#9654; {e(label)}'
            f'<small>{_seconds(path):.1f}s</small></button>')


def _use_html(use):
    e = html.escape
    looped = use.category in LOOPED
    if use.status == GAME:
        names = selection.asset_names(use.key)
        sources = ([" + ".join(take for take, _at in use.recipe)] if use.recipe else use.takes)
        buttons = [_button(f"sounds/{name}", name, f"{name}  <-  {source}", looped)
                   for name, source in zip(names, sources)]
    else:
        buttons = [_button(f"sound_candidates/{take}", take.rsplit("/", 1)[-1], take, looped)
                   for take in use.takes]
    note = f'<span class="note">{e(use.note)}</span>' if use.note else ""
    made = ('<span class="note">put together from ' + e(", ".join(t.rsplit("/", 1)[-1] for t, _ in use.recipe))
            + "</span>") if use.recipe else ""
    return (f'<div class="use"><div class="what">{e(use.label)}'
            f'<span class="badge {BADGE[use.status]}">{e(use.status)}</span>{note}{made}</div>'
            f'<div class="picks">{"".join(buttons)}</div></div>')


def render():
    """The tab's HTML and how many sounds it shows."""
    e = html.escape
    sections, order = {}, []
    for use in selection.USES:
        if use.category not in sections:
            order.append(use.category)
        sections.setdefault(use.category, []).append(use)
    body, total = [], 0
    for category in order:
        uses = sections[category]
        count = sum(1 if u.recipe else len(u.takes) for u in uses)
        total += count
        body.append(f'<section><h2>{e(category)} &middot; {count}</h2>'
                    f'{"".join(_use_html(u) for u in uses)}</section>')
    legend = ('<p class="legend"><span class="badge game">in game</span> the game plays it &nbsp; '
              '<span class="badge ready">ready, not wired</span> chosen, nothing plays it yet &nbsp; '
              '<span class="badge later">future</span> for something the game does not have</p>')
    return legend + "".join(body), total
