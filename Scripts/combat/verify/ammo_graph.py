"""verify.ammo_graph -- what the weapon component's graph does with a gun's
ammunition: the round spent and the deadline pushed as the owning client's
prediction (the server's are the native Server_Fire's since W1: C++,
verify/shot.py), that the reload's arithmetic is nowhere in it (the native
ReloadNow's since W2), a client's picture under ViewRow, and the click and
the clack.

The numbers themselves (magazines, reserves, intervals) are the weapons' own
defaults: verify/weapon_inputs.py. Every check here starts from a named event
or variable (verify/anchor.py), none from a count of the graph.
"""

from combat import fx_vars as FX
from combat.record_vars import VIEW_ROW
from combat.shot_vars import RELOAD_NOW, RELOADED, SERVER_FIRE, SHOT_FIRED
from combat.verify.anchor import (
    event, event_nodes, feeders, pure_feeds, reads, runs, title,
)
from combat.verify.common import by_pins, check, out_pins, past_marks, titled
from combat.verify.fixtures import wg


def _writes(nodes, var):
    """The writes of the item variable ``var`` among ``nodes``."""
    return [n for n in nodes if title(n) == f"Set {var}"]


def _predicted_round():
    """The owning client's predicted round: the Loaded written straight after
    its own Fx_Shot (shot.py), outside any event of the server's."""
    return [n for n in _writes(wg, "Loaded")
            if [title(f) for f in feeders(n, "execute")] == [FX.fx_event(FX.SHOT)]]


def check_ammunition_graph():
    # Each write is found under the event that owns it (shot.py, view.py), so
    # a write another feature adds elsewhere is that feature's to check.
    # The server's round and deadline are the native Server_Fire's (C++): the
    # graph it lets a shot through to writes neither.
    spent = _writes(event_nodes(SHOT_FIRED), "Loaded")
    seen = _writes(event_nodes(VIEW_ROW), "Loaded")
    predicted = _predicted_round()
    check(f"firing spends a round as the owning client's prediction (the server's is "
          f"the native {SERVER_FIRE}'s, not {SHOT_FIRED}'s), and a client's picture "
          "takes the record's",
          not spent and bool(predicted) and bool(seen)
          and all("int - int" in reads(n) for n in predicted)
          and all(f == event(VIEW_ROW) for n in seen for f in feeders(n, "Loaded")),
          f"{SHOT_FIRED} {len(spent)}, predicted {len(predicted)}, {VIEW_ROW} {len(seen)}")
    # The predicted deadline is the one written after the predicted round.
    next_predicted = [n for p in predicted for n in past_marks(runs(p, "then"))
                      if title(n) == "Set NextFireTime"]
    check("the interval pushes NextFireTime as the owning client's predicted deadline "
          f"(the server's is the native {SERVER_FIRE}'s, a reload's the native "
          f"{RELOAD_NOW}'s on the same field)",
          bool(next_predicted) and not _writes(event_nodes(SHOT_FIRED), "NextFireTime")
          and all({"float + float", "GetTimeSeconds"} <= reads(n) for n in next_predicted),
          f"predicted {len(next_predicted)}")
    check("the deadline is compared against the clock, not a frame count",
          bool(titled(wg, "GetTimeSeconds")),
          f"{len(titled(wg, 'GetTimeSeconds'))} GetTimeSeconds")
    # The reserve is only ever *spent*, by the native reload; it is topped up
    # by BP_AmmoPickup. The graph's one write is a client's picture.
    pictured = _writes(event_nodes(VIEW_ROW), "Reserve")
    stray = [n for n in _writes(wg, "Reserve") if n not in pictured]
    check("the weapon component's graph neither spends nor grants the reserve: its "
          "only write is a client's picture of the record",
          bool(pictured) and not stray
          and all(f == event(VIEW_ROW) for n in pictured for f in feeders(n, "Reserve")),
          f"{VIEW_ROW} {len(pictured)}, elsewhere {len(stray)}")
    # The pure-node trap, in the one place where getting it wrong was free
    # ammo: the arithmetic is gone from the graph, not stored in it.
    under = event_nodes(RELOADED)
    wrote = [title(n) for n in under if title(n).startswith("Set")]
    takes = [title(n) for n in wg if "ReloadTake" in title(n).replace(" ", "")]
    check(f"the reload's arithmetic is the native {RELOAD_NOW}'s: the graph has no "
          f"ReloadTake node, and nothing under {RELOADED} writes Loaded, Reserve or "
          "NextFireTime", bool(under) and not wrote and not takes,
          f"{RELOADED}: {len(under)} node(s), writes {wrote}; ReloadTake {takes}")
    endless = [n for n in wg if "InfiniteReserve" in out_pins(n)]
    check("...and the pistol's endless reserve with it: the graph does not read "
          "InfiniteReserve", not endless, f"{len(endless)} read(s)")
    # The gate is nested, not folded: every one of these reads a property off Held,
    # and the outer condition is pulled on frames where nothing is equipped.
    asks = {"the fire gate": [g for d in _dry_plays() for g in feeders(d, "execute")]}
    check("the fire gate asks the weapon whether it uses ammo (the server's own test of "
          "the shot, and the reload's, are the native base's: verify/shot.py)",
          all(any("Get UsesAmmo" in reads(g) for g in v) for v in asks.values()),
          str({k: any("Get UsesAmmo" in reads(g) for g in v) for k, v in asks.items()}))
    fire_gate = asks["the fire gate"]
    check("an unlimited weapon short-circuits the magazine test (an OR, not an AND)",
          bool(fire_gate) and all(
              any(title(n) == "OR Boolean"
                  and any(title(f) == "NOT Boolean" and "Get UsesAmmo" in reads(f)
                          for f in feeders(n, "A") + feeders(n, "B"))
                  for n in pure_feeds(g)) for g in fire_gate),
          str([sorted(reads(g)) for g in fire_gate]))


# ─── The click and the clack ─────────────────────────────────────────────────

def _dry_plays():
    """The plays of Held's DryFireSound: the click."""
    return [n for n in by_pins(wg, "Sound", "Location")
            if [title(f) for f in feeders(n, "Sound")] == ["Get DryFireSound"]]


def check_click_and_clack():
    # Two sounds whose whole value is *when* they do not play. A click on every
    # refused trigger pull would fire on the SMG's every-0.09s cooldown; a clack on
    # every R would reward pressing reload at a full magazine.

    dry = _dry_plays()
    check("the empty chamber clicks",
          bool(dry) and all(title(h) == "Get Held" for d in dry
                            for f in feeders(d, "Sound") for h in feeders(f, "self")),
          f"{len(dry)} play(s) of Held's DryFireSound")
    # The clack is Fx_Reload's (verify/fx.py): told by the server, predicted
    # by the owner, never played at the key.
    clack = [n for n in by_pins(event_nodes(FX.fx_event(FX.RELOAD)), "Sound", "Location")
             if [title(f) for f in feeders(n, "Sound")] == ["Get ReloadSound"]]
    check("the reload clacks", bool(clack),
          f"{len(clack)} play(s) of ReloadSound under {FX.fx_event(FX.RELOAD)}")
    # The gate above it must be an AND, not a bare NOT: "empty" alone would
    # click through every cooldown frame of a held trigger.
    gates = [g for d in dry for g in feeders(d, "execute")]
    conds = [c for g in gates for c in feeders(g, "Condition")]
    check("...behind a Branch whose condition is an AND of two things, so it "
          "stays silent between shots as well as when loaded",
          bool(conds) and all(title(g) == "Branch" for g in gates)
          and all("AND" in title(c).upper() for c in conds),
          str([title(n) for n in gates + conds]))
    # And one of the two has to be the negation of the ammunition test.
    check("...one half of which is \"has no ammunition\"",
          bool(conds) and all(
              any(title(n) == "NOT Boolean" and {"Get Loaded", "Get UsesAmmo"} <= reads(n)
                  for n in pure_feeds(c)) for c in conds),
          str([sorted(reads(c)) for c in conds]))


def run():
    check_ammunition_graph()
    check_click_and_clack()
