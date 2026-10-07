"""verify.strike -- melee, the guard, the fire held out, the throw and the take
as server requests (task M20; combat/strike_vars.py, weapon_component/
punch.py, holds.py, throw.py, pickup.py, combat/item_world.py): the events and
how they travel, what the server asks before it swings or lets an item go,
that a blow is pending and an item in the air only by a Server event, the
owning client's prediction of a swing, and what an item loose in the world
sends every client.

Checked on the compiled classes and the wiring. probes/probe_net_melee.py and
probe_net_throw.py are the two-client proof; the take's own wiring is
verify/pickup.py's.
"""

from uebp import net
from combat import item_vars as IV
from combat.item_world import REPLICATED as ITEM_REPLICATED
from combat.paths import FIRE_WARD_VAR, ITEM_BP_PATH
from combat.strike_vars import (
    SERVER_EVENTS, SERVER_PUNCH, SERVER_SET_HOLDS, SERVER_SLASH, SERVER_TAKE, SERVER_THROW,
    STRIKE_GRACE_S, TABLE, THROW_START_REACH_CM, AskGuard, AskUse, BlockForced, SentGuard,
    SentUse)
from combat.torch_tuning import LIT_VAR
from combat.verify.common import BEL, PIN, by_pins, check, load, num_pin, pin_value
from combat.verify.fixtures import wc, wc_cdo, wg
from combat.verify.record import _authority_branches, _feeders, _title, _upstream
from combat.verify.shot import _asked_above, _calls_of, _event, _gate_arm, _reads_behind
from combat.verify.torch import _served_ward
from combat.weapon_component import vars as WV
from combat.weapon_component.knife import (
    KNIFE_PENDING_VAR, KNIFE_QUEUED_VAR, NEXT_KNIFE_VAR)
from combat.weapon_component.punch import (
    NEXT_PUNCH_VAR, PUNCH_PENDING_VAR, PUNCH_QUEUED_VAR)
from combat.weapon_component.throw_flight import THROWN_VAR

# event -> (its queue, its pending blow, its cooldown, what it must ask first)
SWINGS = {
    SERVER_PUNCH: (PUNCH_QUEUED_VAR, PUNCH_PENDING_VAR, NEXT_PUNCH_VAR,
                   {"Held", "Dead", "Health", "Blocking", NEXT_PUNCH_VAR}),
    SERVER_SLASH: (KNIFE_QUEUED_VAR, KNIFE_PENDING_VAR, NEXT_KNIFE_VAR,
                   {"Held", "Melee", "Dead", "Health", "Blocking", NEXT_KNIFE_VAR}),
}


def _sets(var, value=None):
    return [n for n in wg if _title(n) == f"Set {var}"
            and (value is None or pin_value(n, str(var)) == value)]


def check_events():
    for name in SERVER_EVENTS:
        check(f"{name} is a reliable Server event: the owning client asks, the server "
              "does", _event(name) is not None
              and net.compiled_rpc(wc, name) == (net.SERVER, True),
              str(net.compiled_rpc(wc, name) if _event(name) else None))
    asks = {name: len(_calls_of(name)) for name in SERVER_EVENTS}
    check("the Tick asks for each in one place, where the keys are",
          all(n == 1 for n in asks.values()), str(asks))
    for var, cond, why in ((WV.Blocking, "COND_SKIP_OWNER",
                            "everyone but the owner, who has the key: another "
                            "player's copy poses the guard"),
                           (THROWN_VAR, "COND_OWNER_ONLY",
                            "the owning client alone, whose arc waits for it")):
        got = net.variable_replication(wc, str(var))
        check(f"{var} is Replicated to {why}", got[0] == net.REPLICATED
              and got[2].upper() == cond
              and net.compiled_replication(wc, str(var))[0] == net.REPLICATED, str(got))
    kept = [str(v) for v in TABLE if net.variable_replication(wc, str(v))[0] != net.NONE]
    check("what the client asked and last sent stays on its machine: the server "
          "decides Blocking and FireWard itself, and FireWard goes nowhere",
          not kept and net.variable_replication(wc, FIRE_WARD_VAR)[0] == net.NONE, str(kept))
    check("no key is forced and nothing is asked at the start",
          all(wc_cdo.get_editor_property(str(v)) is False
              for v in (BlockForced, AskGuard, AskUse, SentGuard, SentUse)))


def check_swings():
    gates = _authority_branches()
    for name, (queued, pending, cooldown, want) in SWINGS.items():
        event = _event(name)
        if event is None:
            continue
        raised = _sets(pending, "true")
        check(f"a {pending} is raised in {name} alone: only the machine that owns "
              "the swing ever sweeps", len(raised) == 1 and event in _upstream(raised[0])
              and not any("Tick" in _title(n) for n in _upstream(raised[0])),
              f"{len(raised)} write(s)")
        if len(raised) != 1:
            continue
        asked = _asked_above(raised[0])
        check(f"...and {name} asks first: the hand, a living owner, the guard down "
              "and the cooldown", want <= asked, f"missing {sorted(want - asked)}")
        calls = _calls_of(name)
        cleared = [f for c in calls for f in _upstream(c)
                   if _title(f) == f"Set {queued}" and pin_value(f, queued) in ("false", "")]
        mine = [n for n in _sets(cooldown) if _gate_arm(n, gates) == "else"]
        check(f"the Tick asks once {queued} is cleared, and a client of a server "
              f"stamps its own {cooldown} first, off the authority Branch's false arm",
              len(calls) == 1 and len(cleared) == 1 and len(mine) == 1,
              f"{len(calls)} ask(s), {len(cleared)} clear(s), {len(mine)} predicted stamp(s)")
    graces = [n for n in by_pins(wg, "A", "B")
              if abs((num_pin(n, "B") or 0.0) - STRIKE_GRACE_S) < 1e-9
              and any("GetTimeSeconds" in _title(f).replace(" ", "") for f in _feeders(n, "A"))
              and any(_title(f) in (f"Get {NEXT_PUNCH_VAR}", f"Get {NEXT_KNIFE_VAR}")
                      for q in PIN.list_connected_pins(BEL.find_output_pin(n, "ReturnValue"))
                      for f in _feeders(PIN.get_owning_node(q), "B"))]
    check(f"each swing's cooldown has {STRIKE_GRACE_S:g} s of grace on the server, for "
          "uneven packets", len(graces) == 2, str(len(graces)))


def check_holds():
    event = _event(SERVER_SET_HOLDS)
    told = [n for v in (AskGuard, AskUse) for n in _sets(v)]
    check(f"{SERVER_SET_HOLDS} keeps what it is told ({AskGuard}, {AskUse}) and "
          "decides nothing", len(told) == 2 and all(event in _upstream(n) for n in told),
          f"{len(told)} write(s)")
    calls = _calls_of(SERVER_SET_HOLDS)
    before = {_title(f) for c in calls for f in _upstream(c)}
    check("the owning machine reports the guard and the use key on the frame "
          "either changes, from what it stored",
          len(calls) == 1 and {f"Set {SentGuard}", f"Set {SentUse}"} <= before)
    gates = _authority_branches()
    served = [n for n in _sets(WV.Blocking)
              if any(_title(f) == f"Get {AskGuard}" for a in _feeders(n, str(WV.Blocking))
                     for f in _feeders(a, "A") + _feeders(a, "B"))]
    reads = ({_title(x).replace(" ", "") for n in served
              for a in _feeders(n, str(WV.Blocking)) for b in _feeders(a, "B")
              for x in [b] + _feeders(b, "A") + _feeders(b, "B")
              + [y for z in _feeders(b, "A") + _feeders(b, "B")
                 for y in _feeders(z, "A") + _feeders(z, "B")]})
    check("the server's copy of a client's character is Blocking while the client "
          "asks for it AND the server's own stamina lasts and it is not sprinting, "
          "with authority", len(served) == 1 and _gate_arm(served[0], gates) == "then"
          and any("GetStamina" in t for t in reads) and any("IsSprinting" in t for t in reads),
          str(sorted(reads)))
    wards = [n for n in _sets(FIRE_WARD_VAR) if _served_ward(n)]
    lit = [n for n in wards if [_title(f) for f in _feeders(n, FIRE_WARD_VAR)]
           == [f"Get {LIT_VAR}"]]
    check(f"...and its {FIRE_WARD_VAR} is the use key asked for AND the item in the "
          f"server's own hand {LIT_VAR}, read behind IsValid(Held); lowered on the "
          "other arms", len(wards) == 2 and len(lit) == 1
          and "Held" in _asked_above(lit[0]), f"{len(wards)} write(s), {len(lit)} off Lit")


def check_throw():
    event = _event(SERVER_THROW)
    if event is None:
        return
    lets = [n for n in wg if _title(n) == f"Set {THROWN_VAR}"
            and PIN.list_connected_pins(BEL.find_input_pin(n, THROWN_VAR))]
    check(f"an item is let go in {SERVER_THROW} alone: {THROWN_VAR} is given one by "
          "the machine that owns it", len(lets) == 1 and event in _upstream(lets[0]),
          f"{len(lets)} write(s)")
    if len(lets) != 1:
        return
    asked = _asked_above(lets[0])
    want = {"Held", "Dead", "Health", str(THROWN_VAR)}
    # (A stick is lit within the same 300 cm of a fire: the test wanted is the
    # one a Branch above the release reads.)
    read = [x for b in _upstream(lets[0]) if _title(b) == "Branch"
            for c in _feeders(b, "Condition") for x in [c] + _feeders(c, "A") + _feeders(c, "B")]
    reach = [n for n in by_pins(wg, "A", "B") if num_pin(n, "B") == THROW_START_REACH_CM
             and any("Distance" in _title(f) for f in _feeders(n, "A")) and n in read]
    check("...and the server asks first: an item in a living hand, nothing of this "
          f"player's in the air, and a start within {THROW_START_REACH_CM:g} cm of its "
          "own copy of the thrower", want <= asked and len(reach) == 1,
          f"missing {sorted(want - asked)}, {len(reach)} reach test(s)")
    loosed = {t: [n for n in wg if _title(n).replace(" ", "") == t and event in _upstream(n)]
              for t in ("SetReplicates", "SetReplicateMovement")}
    world = [n for n in _sets(IV.InWorld, "true") if event in _upstream(n)]
    check(f"the release makes the item the world's: {IV.InWorld}, and the server's "
          "actor replicates with its movement from there on",
          all(len(v) == 1 for v in loosed.values()) and len(world) == 1
          and pin_value(loosed["SetReplicates"][0], "bInReplicates") == "true"
          and pin_value(loosed["SetReplicateMovement"][0], "bInReplicateMovement") == "true",
          str({k: len(v) for k, v in loosed.items()}))
    off = [n for n in wg if _title(n).replace(" ", "") == "SetReplicates"
           and pin_value(n, "bInReplicates") != "true"]
    check("...and nothing switches an item's replication off again: the generic "
          "driver would leave each client's copy standing (item_world.py)", not off,
          str(len(off)))
    flights = [n for n in wg if _title(n) == "Branch"
               and str(THROWN_VAR) in {v for c in _feeders(n, "Condition")
                                       for v in _reads_behind(c)}
               and any("HasAuthority" in _title(x).replace(" ", "")
                       for c in _feeders(n, "Condition") for x in _feeders(c, "B"))]
    check("the flight runs only with authority: the owning client has Thrown too, "
          "and flies nothing", len(flights) == 1, str(len(flights)))


def check_item_world():
    item = load(ITEM_BP_PATH)
    got = {str(v): net.variable_replication(item, str(v))[0] for v in ITEM_REPLICATED}
    check("an item's Dropped, Lodged and InWorld, and its Lit and Hot, replicate to "
          "everyone: a client picks up, glimmers, hides, burns and glows by the "
          "server's word",
          all(k == net.REPLICATED for k in got.values())
          and all(net.compiled_replication(item, str(v))[0] == net.REPLICATED
                  for v in ITEM_REPLICATED), str(got))
    check("BP_WeaponItem does not replicate as built: what a player carries is the "
          "record's, and an item starts when it enters the world", not net.replicates(item))
    taken = [n for n in _sets(IV.InWorld) if pin_value(n, IV.InWorld) in ("false", "")]
    check(f"{IV.InWorld} is lowered in {SERVER_TAKE} alone", len(taken) == 1
          and _event(SERVER_TAKE) in _upstream(taken[0]), str(len(taken)))


def run():
    check_events()
    check_swings()
    check_holds()
    check_throw()
    check_item_world()
