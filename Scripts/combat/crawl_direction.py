"""Which way the player crawls, for the stance clips to pose (P2): the weapon
layers' event graph, after GroundSpeed.

    CrawlAhead  = FInterpTo(CrawlAhead,  Velocity . the actor's forward, dt, TURN_SPEED)
    CrawlAcross = FInterpTo(CrawlAcross, Velocity . the actor's right,   dt, TURN_SPEED)
    CrawlMove, CrawlDiag, CrawlSide, CrawlBack, CrawlRight   (crawl_consts.alphas)

crawl_consts.py says why the velocity (every machine has it: nothing new
replicates) and why the pair is eased. Each value is stored and read back
through a getter: a pure node is evaluated once per read, and an eased value
read twice would be eased twice.

Authored each build from nothing: its own nodes (every Set Crawl* and what
feeds one, the update event apart, and the Branch that skips them where
there is no pawn) are taken out first.
"""

from combat import anim_vars as AN
from combat.crawl_consts import CRAWL_FULL_CMS, STEP_GAIN, TURN_SPEED
from combat.player_gait import GROUND_SPEED
from uebp.g import _G
from uebp.graph import BEL, PIN, out, then
from uebp.nodes.actor import FN_ACTOR_FORWARD, FN_ACTOR_RIGHT, FN_VELOCITY
from uebp.nodes.locomotion import FN_TRY_GET_PAWN_OWNER
from uebp.nodes.system import FN_IS_VALID
from uebp.nodes.math import (
    FN_ABS, FN_ADD_FF, FN_CLAMP, FN_DEG_ATAN2, FN_DOT_VV, FN_HYPOTENUSE, FN_INTERP_FF,
    FN_MUL_FF,
)
from uebp.vars import declare_missing

UPDATE_EVENT = "BlueprintUpdateAnimation"
DELTA_PIN = "DeltaTimeX"


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def crawl_sets(events):
    """The Set node of each of the crawl's variables that is in the graph."""
    names = {f"Set {v}" for v in AN.CRAWL}
    return [n for n in events.list_all_nodes() if _title(n) in names]


def _is_event(node):
    return node.get_class().get_name() == "K2Node_Event"


def _feeding(nodes):
    """Every node upstream of ``nodes``' data pins, the events apart."""
    found, stack = {}, list(nodes)
    while stack:
        for p in BEL.list_input_pins(stack.pop()):
            if str(PIN.get_pin_name(p)) == "execute":
                continue
            for q in PIN.list_connected_pins(p):
                up = PIN.get_owning_node(q)
                if not _is_event(up) and up.get_name() not in found:
                    found[up.get_name()] = up
                    stack.append(up)
    return list(found.values())


def _remove_previous(events, after):
    old = crawl_sets(events)
    # The Branch between GroundSpeed and the first of them, and its IsValid.
    old += [PIN.get_owning_node(q) for q in PIN.list_connected_pins(after)
            if PIN.get_owning_node(q).get_class().get_name() == "K2Node_IfThenElse"]
    if old:
        events.remove_nodes(old + [n for n in _feeding(old)
                                   if n.get_name() not in {o.get_name() for o in old}])
    PIN.break_pin_links(after)


def author_crawl_direction(events):
    """The crawl's seven variables, written after GroundSpeed each update."""
    declare_missing(events, AN.CRAWL)
    ground = [n for n in events.list_all_nodes() if _title(n) == f"Set {GROUND_SPEED}"]
    update = [n for n in events.list_all_nodes()
              if _is_event(n) and UPDATE_EVENT in _title(n).replace(" ", "")]
    if len(ground) != 1 or len(update) != 1:
        raise RuntimeError(f"{len(ground)} Set {GROUND_SPEED} and {len(update)} update "
                           "events: weapon_layers._author_ground_speed runs first")
    execs = then(ground[0])
    _remove_previous(events, execs)
    g = _G(events)
    dt = out(update[0], DELTA_PIN)
    pawn = out(g.call(FN_TRY_GET_PAWN_OWNER))
    # An editor preview has no pawn, and reading one that is not there logs.
    execs, _none = g.branch(out(g.call(FN_IS_VALID, Object=pawn)), [execs])

    def clamped(value):
        return out(g.call(FN_CLAMP, Value=value, Min="0.0", Max="1.0"))

    def times(value, by):
        return out(g.call(FN_MUL_FF, A=value, B=str(by)))

    for var, axis in ((AN.CrawlAhead, FN_ACTOR_FORWARD), (AN.CrawlAcross, FN_ACTOR_RIGHT)):
        # A velocity node and an axis node each: a pure node shared by both
        # would be no saving, it is evaluated per read.
        want = g.call(FN_DOT_VV, A=out(g.call(FN_VELOCITY, self=pawn)),
                      B=out(g.call(axis, self=pawn)))
        eased = g.call(FN_INTERP_FF, Current=g.get(var), Target=out(want),
                       DeltaTime=dt, InterpSpeed=str(TURN_SPEED))
        execs = g.put(var, out(eased), [execs])
    speed = g.call(FN_HYPOTENUSE, Width=g.get(AN.CrawlAhead), Height=g.get(AN.CrawlAcross))
    execs = g.put(AN.CrawlMove, clamped(times(out(speed), 1.0 / CRAWL_FULL_CMS)), [execs])
    # 2t: 0 ahead or back, 1 on a diagonal, 2 to a side.
    turn = g.call(FN_DEG_ATAN2, Y=out(g.call(FN_ABS, A=g.get(AN.CrawlAcross))),
                  X=out(g.call(FN_ABS, A=g.get(AN.CrawlAhead))))
    execs = g.put(AN.CrawlDiag, clamped(times(out(turn), 2.0 / 90.0)), [execs])
    turn = g.call(FN_DEG_ATAN2, Y=out(g.call(FN_ABS, A=g.get(AN.CrawlAcross))),
                  X=out(g.call(FN_ABS, A=g.get(AN.CrawlAhead))))
    past = g.call(FN_ADD_FF, A=times(out(turn), 2.0 / 90.0), B="-1.0")
    execs = g.put(AN.CrawlSide, clamped(out(past)), [execs])
    execs = g.put(AN.CrawlBack, clamped(times(g.get(AN.CrawlAhead), -STEP_GAIN)), [execs])
    g.put(AN.CrawlRight, clamped(times(g.get(AN.CrawlAcross), STEP_GAIN)), [execs])
    events.add_comment_to_nodes(
        "Which way the pawn crawls: its velocity ahead and across in its own frame, "
        "eased, and the weights the stance clips blend the eight directions' loops by. "
        "Scripts/combat/crawl_direction.py, crawl_consts.py.", g.made)
