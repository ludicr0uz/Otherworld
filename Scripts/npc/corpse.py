"""The corpse state: the first thing the heartbeat checks once it has a pawn.

    gate(possessed) --> pawn's BP_HealthComponent --> [Dead, or at 0 HP?]
                          no, or no component --> on (stats, patrol/hunt, melee)
                          yes --> Corpse = true --> StopMovement --> log
                                  --> BrainComponent.StopLogic: the tree ends

A dead wanderer used to keep swinging. Its behaviour is one self-re-entering
loop on the AI controller, and nothing in that loop asked whether the pawn was
alive. The only thing ending it was the health component destroying the
controller on death (combat/death.py _author_corpse). Whenever that destroy
was missed or ran late, the ragdolled corpse chased and hit the player. The
ragdoll had rolled away from the capsule, so the attack came from an empty spot.

So death is now a state the loop itself checks, on every pass, before anything
else can run. It runs in the tree's Pulse step (npc/steps.py), and the corpse
branch stops the Behavior Tree itself (StopLogic): nothing is left to run, so a
corpse costs nothing more for the rest of its lifespan.

That left the rest of a pass. The tree runs one step a frame, so a wanderer
killed after its Pulse still had that pass's Chase and Swing to come: a body
already on the ground could land one more blow. So every other step asks the
same question before it does anything (_author_alive_gate, which steps.py puts
at the head of each step event): a dead pawn's step fails without acting, the
pass falls through to the tree's Idle, and the next Pulse ends the tree.

Dead is "the health component says Dead, OR its Health is at zero" in both
gates (_dead_pin): Dead is written by the health component's own Tick, which
on the frame of the killing blow may not have run yet.
"""

from combat.game_state import NPC_ID_VAR
from npc.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from npc.nodes import (
    FN_CONCAT, FN_DISPLAY_NAME, FN_GET_COMP, FN_GET_PAWN, FN_INT_TO_STR,
    FN_IS_VALID, FN_LE_FF, FN_OR, FN_PRINT, FN_STOP_LOGIC, FN_STOP_MOVEMENT,
    NODE_CAST_HEALTH,
)
from npc.paths import (
    CORPSE_LOG_PREFIX, CORPSE_VAR, HEALTH_CLASS_PATH, STEP_RESULT_VAR,
)


def _dead_pin(ed, health_out, keep, x, y):
    """Dead OR Health <= 0, off a health component already cast."""
    dead = keep(_at(ed.add_get_member_variable_node("Dead", HEALTH_CLASS_PATH), x, y))
    _connect(health_out, _pin(dead, "self"))
    hp = keep(_at(ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH),
                  x, y + 140))
    _connect(health_out, _pin(hp, "self"))
    spent = keep(_at(_node(ed, FN_LE_FF), x + 240, y + 140))
    _connect(_pin(hp, "Health", is_input=False), _pin(spent, "A"))
    _set(spent, "B", 0.0)
    either = keep(_at(_node(ed, FN_OR), x + 480, y))
    _connect(_pin(dead, "Dead", is_input=False), _pin(either, "A"))
    _connect(_pin(spent, "ReturnValue", is_input=False), _pin(either, "B"))
    return _pin(either, "ReturnValue", is_input=False)


def _author_alive_gate(ed, exec_in, x0, y0):
    """The head of a step event: a step whose pawn is gone or dead fails here.

        [pawn valid?] no --> StepResult = false
          yes --> pawn's BP_HealthComponent --> [dead?] yes --> StepResult = false
                    no, or no component --> StepResult = false --> the step

    The living arms meet in a StepResult write too, so the step still hangs
    off one exec pin; it is only the default, and every exit of the step
    writes its own. Returns that pin.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    def result(x, y):
        node = keep(_at(ed.add_set_member_variable_node(STEP_RESULT_VAR), x, y))
        _set(node, STEP_RESULT_VAR, "false")
        return node

    pawn = keep(_at(_node(ed, FN_GET_PAWN), x0, y0 + 240))
    pawn_out = _pin(pawn, "ReturnValue", is_input=False)
    there = keep(_at(_node(ed, FN_IS_VALID), x0 + 240, y0 + 240))
    _connect(pawn_out, _pin(there, "Object"))
    possessed = keep(_at(ed.add_branch_node(), x0 + 480, y0))
    _connect(_pin(there, "ReturnValue", is_input=False), _pin(possessed, "Condition"))
    _connect(exec_in, _pin(possessed, "execute"))

    comp = keep(_at(_node(ed, FN_GET_COMP), x0 + 480, y0 + 240))
    _connect(pawn_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    health = keep(_at(_palette(ed, NODE_CAST_HEALTH), x0 + 740, y0))
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(health, "Object"))
    _connect(BEL.find_then_pin(possessed), _pin(health, "execute"))
    health_out = _loose_pin(health, "AsBPHealthComponent", is_input=False)
    is_dead = keep(_at(ed.add_branch_node(), x0 + 1500, y0))
    _connect(_dead_pin(ed, health_out, keep, x0 + 1000, y0 + 240),
             _pin(is_dead, "Condition"))
    _connect(BEL.find_then_pin(health), _pin(is_dead, "execute"))

    refused = result(x0 + 1760, y0 + 300)
    _connect(BEL.find_else_pin(possessed), _pin(refused, "execute"))
    _connect(BEL.find_then_pin(is_dead), _pin(refused, "execute"))
    alive = result(x0 + 1760, y0)
    _connect(BEL.find_else_pin(is_dead), _pin(alive, "execute"))
    _connect(_pin(health, "CastFailed", is_input=False), _pin(alive, "execute"))
    ed.add_comment_to_nodes(
        "Dead, or at 0 HP, or no pawn: this step fails and does nothing.", made)
    return BEL.find_then_pin(alive)


def _author_corpse_gate(ed, exec_in, x0, y0):
    """Stop the heartbeat for good once the pawn is dead.

    Returns ``(nodes, alive, ended)``: the nodes made (for a comment box), the
    exec pins a living wanderer carries on from, and the exec pin after the
    tree has been told to stop.
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

    is_dead = keep(_at(ed.add_branch_node(), x0 + 960, y0))
    _connect(_dead_pin(ed, health_out, keep, x0 + 480, y0 + 240),
             _pin(is_dead, "Condition"))
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
    # The tree ends here. StopLogic called from inside a running task is
    # queued by the BehaviorTreeComponent and applied once the task returns.
    brain = keep(_at(ed.add_get_member_variable_node("BrainComponent"),
                     x0 + 1680, y0 - 200))
    stop = keep(_at(_node(ed, FN_STOP_LOGIC), x0 + 1920, y0))
    _connect(_pin(brain, "BrainComponent", is_input=False), _pin(stop, "self"))
    _set(stop, "Reason", "corpse")
    _connect(BEL.find_then_pin(say), _pin(stop, "execute"))

    ed.add_comment_to_nodes(
        "Corpse state: if this wanderer's pawn is Dead or at 0 HP, mark the controller a "
        "corpse, stop its movement, log it once, and STOP the behaviour tree. "
        "Nothing after this -- patrol, chase, melee -- runs for a corpse.",
        made)
    alive = [BEL.find_else_pin(is_dead), _pin(health, "CastFailed", is_input=False)]
    return made, alive, BEL.find_then_pin(stop)
