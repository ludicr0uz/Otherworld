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
from uebp.graph import BEL, _connect, _loose_pin, _node, _palette, _pin, _set, else_, out, then
from npc.paths import (
    CORPSE_LOG_PREFIX, CORPSE_VAR, HEALTH_CLASS_PATH, STEP_RESULT_VAR,
)
from uebp.nodes.actor import FN_GET_COMP, FN_GET_PAWN, FN_STOP_MOVEMENT
from uebp.nodes.ai import FN_STOP_LOGIC
from uebp.nodes.math import FN_LE_FF, FN_OR
from uebp.nodes.palette import NODE_CAST_HEALTH
from uebp.nodes.system import FN_CONCAT, FN_DISPLAY_NAME, FN_INT_TO_STR, FN_IS_VALID, FN_PRINT


def _dead_pin(ed, health_out, keep):
    """Dead OR Health <= 0, off a health component already cast."""
    dead = keep(ed.add_get_member_variable_node("Dead", HEALTH_CLASS_PATH))
    _connect(health_out, _pin(dead, "self"))
    hp = keep(ed.add_get_member_variable_node("Health", HEALTH_CLASS_PATH))
    _connect(health_out, _pin(hp, "self"))
    spent = keep(_node(ed, FN_LE_FF))
    _connect(out(hp, "Health"), _pin(spent, "A"))
    _set(spent, "B", 0.0)
    either = keep(_node(ed, FN_OR))
    _connect(out(dead, "Dead"), _pin(either, "A"))
    _connect(out(spent), _pin(either, "B"))
    return out(either)


def _author_alive_gate(ed, exec_in):
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

    def result():
        node = keep(ed.add_set_member_variable_node(STEP_RESULT_VAR))
        _set(node, STEP_RESULT_VAR, "false")
        return node

    pawn = keep(_node(ed, FN_GET_PAWN))
    pawn_out = out(pawn)
    there = keep(_node(ed, FN_IS_VALID))
    _connect(pawn_out, _pin(there, "Object"))
    possessed = keep(ed.add_branch_node())
    _connect(out(there), _pin(possessed, "Condition"))
    _connect(exec_in, _pin(possessed, "execute"))

    comp = keep(_node(ed, FN_GET_COMP))
    _connect(pawn_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    health = keep(_palette(ed, NODE_CAST_HEALTH))
    _connect(out(comp), _pin(health, "Object"))
    _connect(then(possessed), _pin(health, "execute"))
    health_out = _loose_pin(health, "AsBPHealthComponent", is_input=False)
    is_dead = keep(ed.add_branch_node())
    _connect(_dead_pin(ed, health_out, keep), _pin(is_dead, "Condition"))
    _connect(then(health), _pin(is_dead, "execute"))

    refused = result()
    _connect(else_(possessed), _pin(refused, "execute"))
    _connect(then(is_dead), _pin(refused, "execute"))
    alive = result()
    _connect(else_(is_dead), _pin(alive, "execute"))
    _connect(out(health, "CastFailed"), _pin(alive, "execute"))
    ed.add_comment_to_nodes(
        "Dead, or at 0 HP, or no pawn: this step fails and does nothing.", made)
    return then(alive)


def _author_corpse_gate(ed, exec_in):
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

    pawn = keep(_node(ed, FN_GET_PAWN))
    pawn_out = out(pawn)
    comp = keep(_node(ed, FN_GET_COMP))
    _connect(pawn_out, _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    health = keep(_palette(ed, NODE_CAST_HEALTH))
    _connect(out(comp), _pin(health, "Object"))
    _connect(exec_in, _pin(health, "execute"))
    health_out = _loose_pin(health, "AsBPHealthComponent", is_input=False)

    is_dead = keep(ed.add_branch_node())
    _connect(_dead_pin(ed, health_out, keep), _pin(is_dead, "Condition"))
    _connect(then(health), _pin(is_dead, "execute"))

    mark = keep(ed.add_set_member_variable_node(CORPSE_VAR))
    _set(mark, CORPSE_VAR, "true")
    _connect(then(is_dead), _pin(mark, "execute"))
    halt = keep(_node(ed, FN_STOP_MOVEMENT))
    _connect(then(mark), _pin(halt, "execute"))

    # "[NPC-CORPSE] #7 BP_ForestWanderer_Zombie_C_3 is a corpse: ..." -- once
    # per death, since the loop ends right after it.
    npc_id = keep(ed.add_get_member_variable_node(NPC_ID_VAR, HEALTH_CLASS_PATH))
    _connect(health_out, _pin(npc_id, "self"))
    id_str = keep(_node(ed, FN_INT_TO_STR))
    _connect(out(npc_id, NPC_ID_VAR), _pin(id_str, "InInt"))
    name = keep(_node(ed, FN_DISPLAY_NAME))
    _connect(pawn_out, _pin(name, "Object"))
    head = keep(_node(ed, FN_CONCAT))
    _set(head, "A", CORPSE_LOG_PREFIX)
    _connect(out(id_str), _pin(head, "B"))
    spaced = keep(_node(ed, FN_CONCAT))
    _connect(out(head), _pin(spaced, "A"))
    _set(spaced, "B", " ")
    named = keep(_node(ed, FN_CONCAT))
    _connect(out(spaced), _pin(named, "A"))
    _connect(out(name), _pin(named, "B"))
    line = keep(_node(ed, FN_CONCAT))
    _connect(out(named), _pin(line, "A"))
    _set(line, "B", " is a corpse: heartbeat stopped, it no longer chases or swings")
    say = keep(_node(ed, FN_PRINT))
    _connect(out(line), _pin(say, "InString"))
    _set(say, "bPrintToScreen", "false")
    _set(say, "bPrintToLog", "true")
    _set(say, "Duration", 0.0)
    _connect(then(halt), _pin(say, "execute"))
    # The tree ends here. StopLogic called from inside a running task is
    # queued by the BehaviorTreeComponent and applied once the task returns.
    brain = keep(ed.add_get_member_variable_node("BrainComponent"))
    stop = keep(_node(ed, FN_STOP_LOGIC))
    _connect(out(brain, "BrainComponent"), _pin(stop, "self"))
    _set(stop, "Reason", "corpse")
    _connect(then(say), _pin(stop, "execute"))

    ed.add_comment_to_nodes(
        "Corpse state: if this wanderer's pawn is Dead or at 0 HP, mark the controller a "
        "corpse, stop its movement, log it once, and STOP the behaviour tree. "
        "Nothing after this -- patrol, chase, melee -- runs for a corpse.",
        made)
    alive = [else_(is_dead), out(health, "CastFailed")]
    return made, alive, then(stop)
