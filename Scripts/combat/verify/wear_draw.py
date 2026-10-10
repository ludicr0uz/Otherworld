"""verify.wear_draw -- a worn garment drawn on the body.

Mirrors weapon_component/wear_draw.py: the DrawWorn event (what it sets on
the garment's component, on and off, and that a dedicated server does none of
it) and its six calls from the wears, the take-off and the drop. Checked on
the wiring; probes/probe_clothing.py wears the jacket and the pants in a game.
"""

from combat.verify.common import check, graph, in_pins, pin_value
from combat.verify.fixtures import wc, wg
from combat.verify.record import _upstream
from combat.verify.wear import _chain, _feeders, _title
from combat.wear_tuning import DRAW_WORN, WORN_VAR
from combat.weapon_component.wear_draw import (
    ITEM_PARAM, ON_PARAM, TICK_ALWAYS, TICK_OPTION_VAR,
)


def _on(n):
    # "" too: a literal equal to its pin's default reads back empty once the
    # graph is loaded from disk (CLAUDE.md).
    return (pin_value(n, ON_PARAM) or "false").lower() == "true"


def check_draw_calls():
    calls = [n for n in wg if _title(n).replace(" ", "") == DRAW_WORN
             and ON_PARAM in in_pins(n)]
    check(f"{DRAW_WORN} is called six times: on by the wear and the dragged wear, off "
          "for the garment each swaps out, by the take-off and by the drop of a worn one",
          sorted(_on(n) for n in calls) == [False, False, False, False, True, True],
          str([pin_value(n, ON_PARAM) for n in calls]))
    check(f"...each handed an {ITEM_PARAM}",
          bool(calls) and all(len(_feeders(n, ITEM_PARAM)) == 1 for n in calls))
    writes = [n for n in wg if "bSizeToFit" in in_pins(n)
              and any(_title(f) == f"Get {WORN_VAR}" for f in _feeders(n, "TargetArray"))]
    # Worn[slot] is a pure read: an off-call fed by it after the slot is
    # rewritten would be handed the new garment, or nothing.
    read = [n for n in calls if any(
        _title(g) == f"Get {WORN_VAR}" for f in _feeders(n, ITEM_PARAM)
        for g in _feeders(f, "TargetArray"))]
    check(f"...and one fed by a read of {WORN_VAR}[slot] is called before the slot is "
          "rewritten, which is the next thing done (the swaps' and the take-off's: "
          "three)",
          len(read) == 3 and all(not _on(n) and _chain(n, 2)[-1] in writes for n in read),
          str([_title(_chain(n, 2)[-1]) for n in read]))


def check_draw_event():
    event = graph(wc).find_event_node(DRAW_WORN)
    check(f"the weapon component has the {DRAW_WORN} event", bool(event))
    if not event:
        return
    body = [n for n in wg if event in _upstream(n)]
    first = [n for n in body if event in _feeders(n, "execute")]
    check("...which first asks whether this is a dedicated server, and draws nothing "
          "on one",
          len(first) == 1 and any("Dedicated" in _title(f).replace(" ", "")
                                  for f in _feeders(first[0], "Condition")),
          str([_title(n) for n in first]))
    meshes = [n for n in body if "NewMesh" in in_pins(n)]
    check("...sets the garment's mesh on its component, and no mesh when it comes off",
          sorted(len(_feeders(n, "NewMesh")) for n in meshes) == [0, 1], str(len(meshes)))
    leads = [n for n in body if "NewLeaderBoneComponent" in in_pins(n)]
    check("...leads it by the body's pose on the body's skeleton only: one leader set, "
          "and cleared for a mesh on its own skeleton and when it comes off",
          sorted(len(_feeders(n, "NewLeaderBoneComponent")) for n in leads) == [0, 0, 1],
          str(len(leads)))
    ticks = [n for n in body if _title(n).startswith("Set")
             and TICK_OPTION_VAR in in_pins(n)]
    check("...poses it whether or not it is rendered, as the body is",
          len(ticks) == 1 and pin_value(ticks[0], TICK_OPTION_VAR) == TICK_ALWAYS,
          str([pin_value(n, TICK_OPTION_VAR) for n in ticks]))
    hides = [n for n in body if "NewHidden" in in_pins(n)]
    check("...and shows it, or hides it again",
          sorted((pin_value(n, "NewHidden") or "false").lower() for n in hides)
          == ["false", "true"], str([pin_value(n, "NewHidden") for n in hides]))


def run():
    check_draw_calls()
    check_draw_event()
