"""verify.ammo_graph -- what the weapon component's graph does with a gun's
ammunition: the round spent and the deadline pushed under Server_Fire and as
the owning client's prediction, the reload's one stored take under ReloadNow,
a client's picture under ViewRow, and the click and the clack.

The numbers themselves (magazines, reserves, intervals) are the weapons' own
defaults: verify/weapon_inputs.py. Every check here starts from a named event
or variable (verify/anchor.py), none from a count of the graph.
"""

from combat import fx_vars as FX
from combat.record_vars import VIEW_ROW
from combat.shot_vars import RELOAD_NOW, SERVER_FIRE
from combat.verify.anchor import (
    event, event_nodes, feeders, in_event, pure_feeds, reads, runs, title,
)
from combat.verify.common import BEL, PIN, by_pins, check, in_pins, out_pins, past_marks, titled
from combat.verify.fixtures import wg


def _linked(node, pin_name):
    """The nodes on the far side of one of ``node``'s output pins."""
    return [PIN.get_owning_node(q)
            for q in PIN.list_connected_pins(BEL.find_output_pin(node, pin_name))]


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
    spent = _writes(event_nodes(SERVER_FIRE), "Loaded")
    filled = _writes(event_nodes(RELOAD_NOW), "Loaded")
    seen = _writes(event_nodes(VIEW_ROW), "Loaded")
    predicted = _predicted_round()
    check("firing spends a round, on the server and as the owning client's "
          "prediction, and reloading puts rounds back (and a client's picture takes "
          "the record's)",
          bool(spent) and bool(predicted) and bool(filled) and bool(seen)
          and all("int - int" in reads(n) for n in spent + predicted)
          and all("int + int" in reads(n) for n in filled)
          and all(f == event(VIEW_ROW) for n in seen for f in feeders(n, "Loaded")),
          f"{SERVER_FIRE} {len(spent)}, predicted {len(predicted)}, "
          f"{RELOAD_NOW} {len(filled)}, {VIEW_ROW} {len(seen)}")
    # The predicted deadline is the one written after the predicted round.
    next_predicted = [n for p in predicted for n in past_marks(runs(p, "then"))
                      if title(n) == "Set NextFireTime"]
    deadlines = {SERVER_FIRE: _writes(event_nodes(SERVER_FIRE), "NextFireTime"),
                 "predicted": next_predicted,
                 RELOAD_NOW: _writes(event_nodes(RELOAD_NOW), "NextFireTime")}
    check("the interval (the server's, and the owning client's predicted one) and the "
          "reload push the same NextFireTime deadline",
          all(deadlines.values())
          and all({"float + float", "GetTimeSeconds"} <= reads(n)
                  for v in deadlines.values() for n in v),
          ", ".join(f"{k} {len(v)}" for k, v in deadlines.items()))
    check("the deadline is compared against the clock, not a frame count",
          bool(titled(wg, "GetTimeSeconds")),
          f"{len(titled(wg, 'GetTimeSeconds'))} GetTimeSeconds")
    # The reserve is only ever *spent* here; it is topped up by BP_AmmoPickup.
    charged = _writes(event_nodes(RELOAD_NOW), "Reserve")
    pictured = _writes(event_nodes(VIEW_ROW), "Reserve")
    check("the weapon component spends the reserve and never grants it (its other "
          "write is a client's picture of the record)",
          bool(charged) and bool(pictured)
          and all("int - int" in reads(n) and "int + int" not in reads(n)
                  for n in charged)
          and all(f == event(VIEW_ROW) for n in pictured for f in feeders(n, "Reserve")),
          f"{RELOAD_NOW}: {[sorted(reads(n)) for n in charged]}")
    # The pure-node trap, in the one place where getting it wrong is free ammo.
    takes = in_event(RELOAD_NOW, "Set ReloadTake")
    check("the reload works out how many rounds move ONCE and stores it",
          bool(takes) and all("Min (Integer)" in reads(n) for n in takes),
          str([sorted(reads(n)) for n in takes]))
    gates = [g for n in takes for g in runs(n, "then") if title(g) == "Branch"]
    back = filled + charged + gates
    check("...and reads it back three times rather than recomputing it",
          bool(filled) and bool(charged) and bool(gates)
          and all("Get ReloadTake" in reads(n) and "Min (Integer)" not in reads(n)
                  for n in back),
          str([(title(n), "Get ReloadTake" in reads(n)) for n in back]))
    check("the reload can never take more than the reserve holds",
          bool(takes) and all({"Min (Integer)", "Get Reserve"} <= reads(n) for n in takes),
          str([sorted(reads(n)) for n in takes]))
    # The pistol's reload: the gap stands in for its reserve (so the magazine
    # fills even from a negative count), and the reserve is written back as is.
    endless = {n.get_path_name(): n for w_ in takes + charged for n in pure_feeds(w_)
               if "InfiniteReserve" in out_pins(n)}
    check("the reload asks InfiniteReserve twice: what it may take, what it is charged",
          bool(takes) and bool(charged)
          and all("Get InfiniteReserve" in reads(n) for n in takes + charged),
          f"{len(endless)} InfiniteReserve read(s) behind ReloadTake and Reserve")
    picks = [c for n in endless.values() for c in _linked(n, "InfiniteReserve")]
    check("...each through a Select, not a branch around the reload",
          bool(picks) and all({"A", "B", "bPickA"} <= in_pins(c) for c in picks),
          str([title(c) for c in picks]))
    # The gate is nested, not folded: every one of these reads a property off Held,
    # and the outer condition is pulled on frames where nothing is equipped.
    asks = {"the fire gate": [g for d in _dry_plays() for g in feeders(d, "execute")],
            SERVER_FIRE: [n for n in event_nodes(SERVER_FIRE) if title(n) == "Branch"],
            RELOAD_NOW: gates}
    check("the fire gate, the server's own test of the shot and the reload each ask "
          "the weapon whether it uses ammo",
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
