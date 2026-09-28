"""The corpse state: the first thing the heartbeat checks once it has a pawn.

    gate(possessed) --> pawn's BP_HealthComponent --> [Dead?]
                          no, or no component --> on (stats, patrol/hunt, melee)
                          yes --> Corpse = true --> StopMovement --> log, and stop

A dead wanderer used to keep swinging. Its behaviour is one self-re-entering
loop on the AI controller, and nothing in that loop asked whether the pawn was
alive. The only thing ending it was the health component destroying the
controller on death (combat/death.py _author_corpse). Whenever that destroy
was missed or ran late, the ragdolled corpse chased and hit the player. The
ragdoll had rolled away from the capsule, so the attack came from an empty spot.

So death is now a state the loop itself checks, on every pass, before anything
else can run. The corpse branch deliberately does not reach the Delay: the loop
ends there, so a corpse costs nothing more for the rest of its lifespan.
"""

from combat.game_state import NPC_ID_VAR
from npc.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from npc.nodes import (
    FN_CONCAT, FN_DISPLAY_NAME, FN_GET_COMP, FN_GET_PAWN, FN_INT_TO_STR,
    FN_PRINT, FN_STOP_MOVEMENT, NODE_CAST_HEALTH,
)
from npc.paths import CORPSE_LOG_PREFIX, CORPSE_VAR, HEALTH_CLASS_PATH


def _author_corpse_gate(ed, exec_in, x0, y0):
    """Stop the heartbeat for good once the pawn is dead.

    Returns ``(nodes, alive)``: the nodes made (for a comment box) and the
    exec pins a living wanderer carries on from.
    """
    ed.remove_member_variable(CORPSE_VAR)
    if not ed.add_member_variable(CORPSE_VAR, BEL.get_basic_type_by_name("bool")):
        raise RuntimeError(f"could not declare {CORPSE_VAR}")

    made = []

    def keep(n):
        made.append(n)
        return n

    pawn = keep(_at(_node(ed, FN_GET_PAWN), x0, y0 + 240))
    pawn_out = _pin(pawn, "ReturnValue", is_input=False)
    comp = keep(_at(_node(ed, FN_GET_COMP), x0 + 240, y0 + 240))
    _connect(pawn_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    health = keep(_at(_palette(ed, NODE_CAST_HEALTH), x0 + 480, y0))
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(health, "Object"))
    _connect(exec_in, _pin(health, "execute"))
    health_out = _loose_pin(health, "AsBPHealthComponent", is_input=False)

    dead = keep(_at(ed.add_get_member_variable_node("Dead", HEALTH_CLASS_PATH),
                    x0 + 720, y0 + 240))
    _connect(health_out, _pin(dead, "self"))
    is_dead = keep(_at(ed.add_branch_node(), x0 + 960, y0))
    _connect(_pin(dead, "Dead", is_input=False), _pin(is_dead, "Condition"))
    _connect(BEL.find_then_pin(health), _pin(is_dead, "execute"))

    mark = keep(_at(ed.add_set_member_variable_node(CORPSE_VAR), x0 + 1200, y0))
    _set(mark, CORPSE_VAR, "true")
    _connect(BEL.find_then_pin(is_dead), _pin(mark, "execute"))
    halt = keep(_at(_node(ed, FN_STOP_MOVEMENT), x0 + 1440, y0))
    _connect(BEL.find_then_pin(mark), _pin(halt, "execute"))

    # "[NPC-CORPSE] #7 BP_ForestWanderer_Zombie_C_3 is a corpse: ..." -- once
    # per death, since the loop ends right after it.
    npc_id = keep(_at(ed.add_get_member_variable_node(NPC_ID_VAR, HEALTH_CLASS_PATH),
                      x0 + 1200, y0 + 360))
    _connect(health_out, _pin(npc_id, "self"))
    id_str = keep(_at(_node(ed, FN_INT_TO_STR), x0 + 1440, y0 + 360))
    _connect(_pin(npc_id, NPC_ID_VAR, is_input=False), _pin(id_str, "InInt"))
    name = keep(_at(_node(ed, FN_DISPLAY_NAME), x0 + 1440, y0 + 480))
    _connect(pawn_out, _pin(name, "Object"))
    head = keep(_at(_node(ed, FN_CONCAT), x0 + 1680, y0 + 360))
    _set(head, "A", CORPSE_LOG_PREFIX)
    _connect(_pin(id_str, "ReturnValue", is_input=False), _pin(head, "B"))
    spaced = keep(_at(_node(ed, FN_CONCAT), x0 + 1920, y0 + 360))
    _connect(_pin(head, "ReturnValue", is_input=False), _pin(spaced, "A"))
    _set(spaced, "B", " ")
    named = keep(_at(_node(ed, FN_CONCAT), x0 + 2160, y0 + 360))
    _connect(_pin(spaced, "ReturnValue", is_input=False), _pin(named, "A"))
    _connect(_pin(name, "ReturnValue", is_input=False), _pin(named, "B"))
    line = keep(_at(_node(ed, FN_CONCAT), x0 + 2400, y0 + 360))
    _connect(_pin(named, "ReturnValue", is_input=False), _pin(line, "A"))
    _set(line, "B", " is a corpse: heartbeat stopped, it no longer chases or swings")
    say = keep(_at(_node(ed, FN_PRINT), x0 + 1680, y0))
    _connect(_pin(line, "ReturnValue", is_input=False), _pin(say, "InString"))
    _set(say, "bPrintToScreen", "false")
    _set(say, "bPrintToLog", "true")
    _set(say, "Duration", 0.0)
    _connect(BEL.find_then_pin(halt), _pin(say, "execute"))
    # say's `then` is left unconnected on purpose: that is the loop ending.

    ed.add_comment_to_nodes(
        "Corpse state: if this wanderer's pawn is Dead, mark the controller a "
        "corpse, stop its movement, log it once, and END the heartbeat (no "
        "Delay). Nothing after this -- patrol, chase, melee -- runs for a corpse.",
        made)
    alive = [BEL.find_else_pin(is_dead), _pin(health, "CastFailed", is_input=False)]
    return made, alive
