"""Interact: the key acts on ONE thing in reach, the one nearest the reticle.

The key knows nothing about what it acts on. Each kind of thing that can be
interacted with is a pair in KINDS:

  candidates(ed, exec_in)               walks the things of its kind and hands
                                        back each one, whether it is offered
                                        at all, and the exec pins of the walk
  act(ed, target, exec_in)              casts InteractTarget to its kind and
                                        does its thing to it

A press runs every kind's walk in turn. A candidate that is offered and lies
within INTERACT_RADIUS of the player, and within INTERACT_HEIGHT of it
up or down, is kept in InteractTarget when it is
nearer AimPoint, the point the reticle rests on (aim.py resolves it every
frame, armed or not), than the one kept so far. Nothing is done inside a walk.
After the last one the target goes down the kinds' acts in order, and the first
whose cast takes it acts on it, once. Today there are two kinds: an item
lying on the ground, which is picked up (pickup.py), and a campfire, which
heats the knife or the axe in hand (heat.py). A new kind is a new pair.

InteractForced is the probe's stand-in for the key press: no key can be
injected into a headless game (probes/probe_pickup.py). It is OR'd with the
key, the press clears it, and it is false in every real game.
"""

from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from combat.nodes import (
    FN_ABS, FN_ACTOR_LOC, FN_AND, FN_BREAK_VECTOR, FN_DISTANCE, FN_IS_VALID,
    FN_LESS_FF, FN_OR, FN_SUB_VV,
)
from combat.tuning import INTERACT_KEY, INTERACT_RADIUS
from combat.weapon_component.heat import _author_fire_candidates, _author_heat_item
from combat.weapon_component.pickup import _author_item_candidates, _author_take_item

INTERACT_TARGET_VAR = "InteractTarget"   # the nearest candidate so far, or None
INTERACT_GAP_VAR = "InteractGap"         # its distance to AimPoint, cm
INTERACT_FORCED_VAR = "InteractForced"   # a probe pressing the key
# What InteractGap starts a search at: farther than any candidate can be from
# the aim point, which is at most the aim trace's kilometre out.
INTERACT_NO_GAP = 1.0e9
# How far above or below the player's middle (the capsule's centre, about 90 cm
# up when standing) a candidate may lie and still be in reach. The radius alone
# is a sphere, so an item on a ledge or down a drop 2 m off was still taken.
# 150 cm reaches the ground under a standing player with room for a slope, and
# no higher than an arm's length over the head.
INTERACT_HEIGHT = 150.0
# What the key and its variables were called while all it did was pick up an
# item. build.py takes them off a component built before the rename.
RETIRED_VARS = ("KeyPickup", "PickBest", "PickBestGap", "PickupForced")

# (candidates, act) per kind of thing the key acts on, in the order their
# casts are tried.
KINDS = ((_author_item_candidates, _author_take_item),
         (_author_fire_candidates, _author_heat_item))


def _author_offer(ed, owner, candidate, offered, exec_in):
    """One candidate of a walk: keep it if it is in reach and the nearest yet."""
    made = []

    def keep(n):
        made.append(n)
        return n

    there = keep(_node(ed, FN_ACTOR_LOC))
    _connect(candidate, _pin(there, "self"))
    here = keep(_node(ed, FN_ACTOR_LOC))
    _connect(owner, _pin(here, "self"))
    gap = keep(_node(ed, FN_DISTANCE))
    _connect(out(there, "ReturnValue"), _pin(gap, "V1"))
    _connect(out(here, "ReturnValue"), _pin(gap, "V2"))
    near = keep(_node(ed, FN_LESS_FF))
    _connect(out(gap, "ReturnValue"), _pin(near, "A"))
    _set(near, "B", INTERACT_RADIUS)
    # And how far up or down: |dz| < INTERACT_HEIGHT.
    rise = keep(_node(ed, FN_SUB_VV))
    _connect(out(there, "ReturnValue"), _pin(rise, "A"))
    _connect(out(here, "ReturnValue"), _pin(rise, "B"))
    parts = keep(_node(ed, FN_BREAK_VECTOR))
    _connect(out(rise, "ReturnValue"), _pin(parts, "InVec"))
    dz = keep(_node(ed, FN_ABS))
    _connect(out(parts, "Z"), _pin(dz, "A"))
    level = keep(_node(ed, FN_LESS_FF))
    _connect(out(dz, "ReturnValue"), _pin(level, "A"))
    _set(level, "B", INTERACT_HEIGHT)

    # How far the candidate lies from the point the reticle rests on. Pure, so
    # the Branch and the Set below each compute it, from inputs that do not
    # change in between.
    aim = keep(ed.add_get_member_variable_node("AimPoint"))
    aim_gap = keep(_node(ed, FN_DISTANCE))
    _connect(out(there, "ReturnValue"), _pin(aim_gap, "V1"))
    _connect(out(aim, "AimPoint"), _pin(aim_gap, "V2"))
    best_gap = keep(ed.add_get_member_variable_node(INTERACT_GAP_VAR))
    closer = keep(_node(ed, FN_LESS_FF))
    _connect(out(aim_gap, "ReturnValue"), _pin(closer, "A"))
    _connect(out(best_gap, INTERACT_GAP_VAR), _pin(closer, "B"))

    and1 = keep(_node(ed, FN_AND))
    _connect(offered, _pin(and1, "A"))
    _connect(out(near, "ReturnValue"), _pin(and1, "B"))
    and_h = keep(_node(ed, FN_AND))
    _connect(out(and1, "ReturnValue"), _pin(and_h, "A"))
    _connect(out(level, "ReturnValue"), _pin(and_h, "B"))
    and2 = keep(_node(ed, FN_AND))
    _connect(out(and_h, "ReturnValue"), _pin(and2, "A"))
    _connect(out(closer, "ReturnValue"), _pin(and2, "B"))

    # The walk only remembers. Acting inside it is how one press used to pick
    # up every item in reach.
    better = keep(ed.add_branch_node())
    _connect(out(and2, "ReturnValue"), _pin(better, "Condition"))
    _connect(exec_in, _pin(better, "execute"))
    remember = keep(ed.add_set_member_variable_node(INTERACT_TARGET_VAR))
    _connect(candidate, _pin(remember, INTERACT_TARGET_VAR))
    _connect(then(better), _pin(remember, "execute"))
    at_gap = keep(ed.add_set_member_variable_node(INTERACT_GAP_VAR))
    _connect(out(aim_gap, "ReturnValue"), _pin(at_gap, INTERACT_GAP_VAR))
    _connect(then(remember), _pin(at_gap, "execute"))

    ed.add_comment_to_nodes(
        f"A candidate the walk offers, within {INTERACT_RADIUS:.0f} cm of the "
        f"player and {INTERACT_HEIGHT:.0f} cm of it up or down, is kept as InteractTarget when it is nearer AimPoint, the "
        "point the reticle rests on, than the one kept so far. The walk only "
        "remembers it.",
        made)


def _author_interact(ed, owner, pressed, exec_ins):
    """E: act on the thing in reach nearest the reticle's point.

    Returns (acted, idle): the exec pins a press that did something leaves by,
    and the ones every other frame leaves by.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    forced = keep(ed.add_get_member_variable_node(INTERACT_FORCED_VAR))
    wants = keep(_node(ed, FN_OR))
    _connect(pressed, _pin(wants, "A"))
    _connect(out(forced, INTERACT_FORCED_VAR), _pin(wants, "B"))
    gate = keep(ed.add_branch_node())
    _connect(out(wants, "ReturnValue"), _pin(gate, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(gate, "execute"))

    spent = keep(ed.add_set_member_variable_node(INTERACT_FORCED_VAR))
    _set(spent, INTERACT_FORCED_VAR, "false")
    _connect(then(gate), _pin(spent, "execute"))
    # InteractTarget is set with its input pin left unconnected, which is how
    # a Blueprint object variable is cleared to None.
    forget = keep(ed.add_set_member_variable_node(INTERACT_TARGET_VAR))
    _connect(then(spent), _pin(forget, "execute"))
    far = keep(ed.add_set_member_variable_node(INTERACT_GAP_VAR))
    _set(far, INTERACT_GAP_VAR, INTERACT_NO_GAP)
    _connect(then(forget), _pin(far, "execute"))

    # --- the search: every kind's walk in turn, each offering its candidates --
    flow = then(far)
    for candidates, _act in KINDS:
        candidate, offered, body, flow = candidates(ed, flow)
        _author_offer(ed, owner, candidate, offered, body)

    # --- after the search: the kinds try the one that was kept, in order ------
    target_get = keep(ed.add_get_member_variable_node(INTERACT_TARGET_VAR))
    target = out(target_get, INTERACT_TARGET_VAR)
    any_target = keep(_node(ed, FN_IS_VALID))
    _connect(target, _pin(any_target, "Object"))
    found = keep(ed.add_branch_node())
    _connect(out(any_target, "ReturnValue"), _pin(found, "Condition"))
    _connect(flow, _pin(found, "execute"))

    acted, idle = (), (else_(gate), else_(found))
    flow = then(found)
    for _candidates, act in KINDS:
        did, did_not, flow = act(ed, target, flow)
        acted += did
        idle += did_not
    idle += (flow,)   # a target no kind's cast took

    ed.add_comment_to_nodes(
        f"{INTERACT_KEY} interacts with ONE thing: of the candidates the kinds "
        f"offer within {INTERACT_RADIUS:.0f} cm of the player, the one nearest "
        "AimPoint, the point the reticle rests on (InteractTarget). The act "
        "runs once, after the search, by the kind whose cast takes the target. "
        "An item lying there is picked up; a campfire heats the blade in hand.",
        made)
    return acted, idle
