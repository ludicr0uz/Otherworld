"""Who a wanderer means by "the player": the controller's Target, chosen
among every living player and kept (task M27). Every other step reads it
(``target``); none asks for a player itself, and none reads player 0.

    BT_PlayerPresent (Notice's head: on patrol, not Aggro)
        -> TargetNear = the living players within NPC_TARGET_SCAN_CM
        -> [any?] yes: Target = TargetNear[TargetScan % their count],
                       TargetScan + 1      (each in turn, a pass apiece)
                  no:  Target = the nearest living player, however far
        -> [Target is someone?] succeed: the senses test them / fail: patrol

    BT_Target (Hunt's head: Aggro)
        -> [Target is still among the living players?]   succeed: kept
        -> Target = the nearest living player
        -> [someone?] no: fail (the pass falls through to the patrol; it
                          is still Aggro, and hunts the first to live again)
                      yes: the hunt starts over (``restart``: a stalker
                           roars at the new one)                 succeed

    the hurt sense (npc/senses.py), as it answers yes:
        -> [the pawn of whoever struck the last blow is there?]
               Target = them (``_author_blame``)

    the sound sense, as it answers yes (M28):
        -> [the pawn that made the noise it heard is there?]
               Target = them (``_author_take``)

On patrol the candidate changes every pass, so a sense fires at whoever it
is true of, not at whoever stands nearest: a player in the sight cone is seen
though another stands closer behind the wanderer's back. The sense that fires
leaves its candidate in Target, and Aggro keeps them from then on. A player
is living while LivingPlayers says so (net/players.py): one who died
(PlayerDead) or left (no pawn) is gone from it, and that is the switch.

In single player the one player is every answer here, as before.
"""

from forest_generator.npc_agro import NPC_TARGET_SCAN_CM
from net.players import _for_each, living_players, nearest_living_player, player_pin
from npc import controller_vars as NV
from npc.graph import _Graph
from npc.paths import TARGET_NEAR_VAR, TARGET_SCAN_VAR, TARGET_VAR
from uebp.graph import _connect, _pin, else_, out, then
from uebp.nodes.actor import FN_ACTOR_LOC, FN_GET_PAWN
from uebp.nodes.array import (
    FN_ARR_ADD, FN_ARR_CLEAR, FN_ARR_CONTAINS, FN_ARR_GET, FN_ARR_LEN)
from uebp.nodes.math import FN_ADD_II, FN_DISTANCE, FN_GREATER_II, FN_LE_FF, FN_MOD_II
from uebp.nodes.system import FN_IS_VALID
from uebp.vars import declare

# On the health component's native parent (Source/Otherworld): the controller
# of whoever struck the last blow. The server's alone, as this graph is.
LAST_INSTIGATOR_PROP = "LastInstigator"
HEALTH_NATIVE_CLASS_PATH = "/Script/Otherworld.OtherworldHealthComponent"


def declare_target_vars(ed):
    """No one, no one near, the first turn."""
    declare(ed, NV.TARGET)


def target(ed):
    """A read of Target; the pawn is ``target_pin(node)``. Someone in every
    step the tree runs after BT_PlayerPresent or BT_Target succeeded."""
    return ed.add_get_member_variable_node(TARGET_VAR)


def target_pin(node):
    return out(node, TARGET_VAR)


def _here(g):
    pawn = g.call(FN_GET_PAWN)
    here = g.call(FN_ACTOR_LOC)
    _connect(out(pawn), _pin(here, "self"))
    return out(here)


def _someone(g, exec_in):
    """The Branch on "Target is someone"."""
    there = g.call(FN_IS_VALID)
    _connect(g.get(TARGET_VAR), _pin(there, "Object"))
    return g.branch(out(there), exec_in)


def _author_candidate(ed, exec_in, yes_in, no_in):
    """BT_PlayerPresent: the player this pass's senses are asked about."""
    g = _Graph(ed)
    here = _here(g)
    living, players = living_players(ed, [exec_in])
    g.keep(living)
    wipe = g.call(FN_ARR_CLEAR)
    _connect(g.get(TARGET_NEAR_VAR), _pin(wipe, "TargetArray"))
    _connect(then(living), _pin(wipe, "execute"))
    one, body, done, loop = _for_each(ed, players, [then(wipe)])
    g.keep(loop)
    there = g.call(FN_ACTOR_LOC)
    _connect(one, _pin(there, "self"))
    gap = g.call(FN_DISTANCE)
    _connect(here, _pin(gap, "V1"))
    _connect(out(there), _pin(gap, "V2"))
    near = g.branch(g.op(FN_LE_FF, out(gap), NPC_TARGET_SCAN_CM), body)
    add = g.call(FN_ARR_ADD)
    _connect(g.get(TARGET_NEAR_VAR), _pin(add, "TargetArray"))
    _connect(one, _pin(add, "NewItem"))
    _connect(then(near), _pin(add, "execute"))

    count = g.call(FN_ARR_LEN)
    _connect(g.get(TARGET_NEAR_VAR), _pin(count, "TargetArray"))
    any_near = g.branch(g.op(FN_GREATER_II, out(count), 0), done)
    # Their turn: one read of the array, in the Set, before the turn moves on.
    turn = g.op(FN_MOD_II, g.get(TARGET_SCAN_VAR), out(count))
    pick = g.call(FN_ARR_GET)
    _connect(g.get(TARGET_NEAR_VAR), _pin(pick, "TargetArray"))
    _connect(turn, _pin(pick, "Index"))
    took = g.put(TARGET_VAR, then(any_near), pin=out(pick, "Item"))
    moved = g.put(TARGET_SCAN_VAR, took, pin=g.op(FN_ADD_II, g.get(TARGET_SCAN_VAR), 1))
    # No one inside the scan: the nearest, so a shot heard or felt from far
    # off still has someone to be laid on. None while no player lives.
    nearest = g.keep(nearest_living_player(ed, here))
    far = g.put(TARGET_VAR, else_(any_near), pin=player_pin(nearest))

    someone = _someone(g, [moved, far])
    _connect(then(someone), yes_in)
    _connect(else_(someone), no_in)
    return g.made


def _author_keep(ed, exec_in, yes_in, no_in, restart=()):
    """BT_Target: the hunted player while they live, the nearest living one
    once they do not. ``restart`` is ``(variable, value)`` pairs written at a
    switch: what the hunt of the last target left behind."""
    g = _Graph(ed)
    living, players = living_players(ed, [exec_in])
    g.keep(living)
    has = g.call(FN_ARR_CONTAINS)
    _connect(players, _pin(has, "TargetArray"))
    _connect(g.get(TARGET_VAR), _pin(has, "ItemToFind"))
    kept = g.branch(out(has), then(living))
    _connect(then(kept), yes_in)

    nearest = g.keep(nearest_living_player(ed, _here(g)))
    step = g.put(TARGET_VAR, else_(kept), pin=player_pin(nearest))
    someone = _someone(g, step)
    _connect(else_(someone), no_in)
    step = then(someone)
    for var, value in restart:
        step = g.put(var, step, literal=value)
    _connect(step, yes_in)
    return g.made


def _author_blame(ed, exec_in, health_pin):
    """The hurt sense's yes: Target is whoever struck the last blow, if their
    pawn is there (a blow from a body since destroyed leaves the candidate).
    Returns ``(nodes, the exec pin after)``."""
    g = _Graph(ed)
    by = g.keep(ed.add_get_member_variable_node(LAST_INSTIGATOR_PROP, HEALTH_NATIVE_CLASS_PATH))
    _connect(health_pin, _pin(by, "self"))
    named = g.call(FN_IS_VALID)
    _connect(out(by, LAST_INSTIGATOR_PROP), _pin(named, "Object"))
    known = g.branch(out(named), exec_in)
    pawn = g.call(FN_GET_PAWN)
    _connect(out(by, LAST_INSTIGATOR_PROP), _pin(pawn, "self"))
    took, taken = _author_take(ed, then(known), out(pawn))
    join = g.branch(None, [taken, else_(known)])
    return g.made + took, then(join)


def _author_take(ed, exec_in, pawn_pin):
    """Target is ``pawn_pin``'s pawn if it is there; the candidate stays if
    not. The hurt sense's striker and the sound sense's noise-maker (M28).
    Returns ``(nodes, the exec pin after)``."""
    g = _Graph(ed)
    bodied = g.call(FN_IS_VALID)
    _connect(pawn_pin, _pin(bodied, "Object"))
    there = g.branch(out(bodied), exec_in)
    taken = g.put(TARGET_VAR, then(there), pin=pawn_pin)
    join = g.branch(None, [taken, else_(there)])
    return g.made, then(join)
