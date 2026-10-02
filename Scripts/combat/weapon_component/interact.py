"""Interact: the key acts on ONE thing in reach, the one nearest the reticle.

The key knows nothing about what it acts on. Each kind of thing that can be
interacted with is a pair in KINDS:

  candidates(ed, exec_in, x0, y0)       walks the things of its kind and hands
                                        back each one, whether it is offered
                                        at all, and the exec pins of the walk
  act(ed, target, exec_in, x0, y0)      casts InteractTarget to its kind and
                                        does its thing to it

A press runs every kind's walk in turn. A candidate that is offered and lies
within INTERACT_RADIUS of the player is kept in InteractTarget when it is
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

from combat.graph import BEL, _at, _connect, _node, _pin, _set
from combat.nodes import (
    FN_ACTOR_LOC, FN_AND, FN_DISTANCE, FN_IS_VALID, FN_LESS_FF, FN_OR,
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
# What the key and its variables were called while all it did was pick up an
# item. build.py takes them off a component built before the rename.
RETIRED_VARS = ("KeyPickup", "PickBest", "PickBestGap", "PickupForced")

# (candidates, act) per kind of thing the key acts on, in the order their
# casts are tried.
KINDS = ((_author_item_candidates, _author_take_item),
         (_author_fire_candidates, _author_heat_item))
KIND_PITCH = 2000   # graph units between two kinds' rows of nodes


def _out(node, name):
    return _pin(node, name, is_input=False)


def _author_offer(ed, owner, candidate, offered, exec_in, x0, y0):
    """One candidate of a walk: keep it if it is in reach and the nearest yet."""
    made = []

    def keep(n):
        made.append(n)
        return n

    there = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 1900, y0 + 400))
    _connect(candidate, _pin(there, "self"))
    here = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 1900, y0 + 520))
    _connect(owner, _pin(here, "self"))
    gap = keep(_at(_node(ed, FN_DISTANCE), x0 + 2160, y0 + 440))
    _connect(_out(there, "ReturnValue"), _pin(gap, "V1"))
    _connect(_out(here, "ReturnValue"), _pin(gap, "V2"))
    near = keep(_at(_node(ed, FN_LESS_FF), x0 + 2400, y0 + 440))
    _connect(_out(gap, "ReturnValue"), _pin(near, "A"))
    _set(near, "B", INTERACT_RADIUS)

    # How far the candidate lies from the point the reticle rests on. Pure, so
    # the Branch and the Set below each compute it, from inputs that do not
    # change in between.
    aim = keep(_at(ed.add_get_member_variable_node("AimPoint"), x0 + 1900, y0 + 660))
    aim_gap = keep(_at(_node(ed, FN_DISTANCE), x0 + 2160, y0 + 620))
    _connect(_out(there, "ReturnValue"), _pin(aim_gap, "V1"))
    _connect(_out(aim, "AimPoint"), _pin(aim_gap, "V2"))
    best_gap = keep(_at(ed.add_get_member_variable_node(INTERACT_GAP_VAR),
                        x0 + 2160, y0 + 780))
    closer = keep(_at(_node(ed, FN_LESS_FF), x0 + 2400, y0 + 620))
    _connect(_out(aim_gap, "ReturnValue"), _pin(closer, "A"))
    _connect(_out(best_gap, INTERACT_GAP_VAR), _pin(closer, "B"))

    and1 = keep(_at(_node(ed, FN_AND), x0 + 2640, y0 + 340))
    _connect(offered, _pin(and1, "A"))
    _connect(_out(near, "ReturnValue"), _pin(and1, "B"))
    and2 = keep(_at(_node(ed, FN_AND), x0 + 2880, y0 + 420))
    _connect(_out(and1, "ReturnValue"), _pin(and2, "A"))
    _connect(_out(closer, "ReturnValue"), _pin(and2, "B"))

    # The walk only remembers. Acting inside it is how one press used to pick
    # up every item in reach.
    better = keep(_at(ed.add_branch_node(), x0 + 3120, y0))
    _connect(_out(and2, "ReturnValue"), _pin(better, "Condition"))
    _connect(exec_in, _pin(better, "execute"))
    remember = keep(_at(ed.add_set_member_variable_node(INTERACT_TARGET_VAR),
                        x0 + 3380, y0))
    _connect(candidate, _pin(remember, INTERACT_TARGET_VAR))
    _connect(BEL.find_then_pin(better), _pin(remember, "execute"))
    at_gap = keep(_at(ed.add_set_member_variable_node(INTERACT_GAP_VAR), x0 + 3640, y0))
    _connect(_out(aim_gap, "ReturnValue"), _pin(at_gap, INTERACT_GAP_VAR))
    _connect(BEL.find_then_pin(remember), _pin(at_gap, "execute"))

    ed.add_comment_to_nodes(
        f"A candidate the walk offers, within {INTERACT_RADIUS:.0f} cm of the "
        "player, is kept as InteractTarget when it is nearer AimPoint, the "
        "point the reticle rests on, than the one kept so far. The walk only "
        "remembers it.",
        made)


def _author_interact(ed, owner, pressed, exec_ins, x0, y0):
    """E: act on the thing in reach nearest the reticle's point.

    Returns (acted, idle): the exec pins a press that did something leaves by,
    and the ones every other frame leaves by.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    forced = keep(_at(ed.add_get_member_variable_node(INTERACT_FORCED_VAR),
                      x0 - 560, y0 + 280))
    wants = keep(_at(_node(ed, FN_OR), x0 - 280, y0 + 160))
    _connect(pressed, _pin(wants, "A"))
    _connect(_out(forced, INTERACT_FORCED_VAR), _pin(wants, "B"))
    gate = keep(_at(ed.add_branch_node(), x0, y0))
    _connect(_out(wants, "ReturnValue"), _pin(gate, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(gate, "execute"))

    spent = keep(_at(ed.add_set_member_variable_node(INTERACT_FORCED_VAR), x0 + 260, y0))
    _set(spent, INTERACT_FORCED_VAR, "false")
    _connect(BEL.find_then_pin(gate), _pin(spent, "execute"))
    # InteractTarget is set with its input pin left unconnected, which is how
    # a Blueprint object variable is cleared to None.
    forget = keep(_at(ed.add_set_member_variable_node(INTERACT_TARGET_VAR),
                      x0 + 520, y0))
    _connect(BEL.find_then_pin(spent), _pin(forget, "execute"))
    far = keep(_at(ed.add_set_member_variable_node(INTERACT_GAP_VAR), x0 + 780, y0))
    _set(far, INTERACT_GAP_VAR, INTERACT_NO_GAP)
    _connect(BEL.find_then_pin(forget), _pin(far, "execute"))

    # --- the search: every kind's walk in turn, each offering its candidates --
    flow = BEL.find_then_pin(far)
    for i, (candidates, _act) in enumerate(KINDS):
        y = y0 + i * KIND_PITCH
        candidate, offered, body, flow = candidates(ed, flow, x0, y)
        _author_offer(ed, owner, candidate, offered, body, x0, y)

    # --- after the search: the kinds try the one that was kept, in order ------
    y1 = y0 + (len(KINDS) - 1) * KIND_PITCH + 1000
    target_get = keep(_at(ed.add_get_member_variable_node(INTERACT_TARGET_VAR),
                          x0 + 1320, y1 + 260))
    target = _out(target_get, INTERACT_TARGET_VAR)
    any_target = keep(_at(_node(ed, FN_IS_VALID), x0 + 1580, y1 + 260))
    _connect(target, _pin(any_target, "Object"))
    found = keep(_at(ed.add_branch_node(), x0 + 1840, y1))
    _connect(_out(any_target, "ReturnValue"), _pin(found, "Condition"))
    _connect(flow, _pin(found, "execute"))

    acted, idle = (), (BEL.find_else_pin(gate), BEL.find_else_pin(found))
    flow = BEL.find_then_pin(found)
    for i, (_candidates, act) in enumerate(KINDS):
        did, did_not, flow = act(ed, target, flow, x0, y1 + i * KIND_PITCH)
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
