"""Save and exit's countdown: the character's own, started by AskSaveExit.

    AskSaveExit (the M panel's row, through the HUD): alive and no exit
        running -> ExitPending, ExitStartedAt = now, ExitAt = now +
        EXIT_SECONDS, ExitDue = false

    every Tick of a living owner, on every copy (the head of the upkeep),
    while ExitPending:
        hit since it started (the owner's BP_HealthComponent.LastDamageTime,
        stamped by the wanderers' swing), OR a move key down (the pawn's
        last movement input: the character's input still reaches the pawn
        while its movement is disabled, and the movement component consumes
        it before it looks at the mode), OR the trigger pressed this frame
        (the trigger's tap, trigger.py; a probe's FireForced too), OR the
        owner off the ground (its movement not walking: a jump, a climb, an
        exit asked for in the air)
            -> called off: ExitPending = false, ExitCalledOffAt = now
        ExitAt passed -> ExitPending = false, ExitDue = true
        else nothing: the character waits

Nothing holds the character still, because nothing has to: whatever would
move it calls the exit off, and one that was moving when it asked brakes to
a stand by itself. Its movement stays in the walking mode on purpose. Until
13 Oct 2026 the countdown disabled it every Tick (DisableMovement, the mode
MOVE_None), and the motion matching's Foot Placement node reads that mode as
"in the air" and stops fitting the feet to the ground: on a slope the legs
snapped to the flat pose as the countdown began (one foot 39 cm off the
ground it stood on, measured on a 25 degree slope) and back when it was
called off. probes/probe_save_exit_legs.py holds the feet to where they
stood. The stance keys still work during the countdown, in place.

The component decides that the exit is due and nothing more. What leaving is
belongs to whoever watches ExitDue: in single player the HUD writes the
profile and reopens the level (graphics_menu/save_exit.py); as a client of a
server the HUD asks the same way, of the client's own copy, and disconnects
(graphics_menu/mode_tick.py), and the save is the server's (M35). The dead gate lowers ExitPending (dead.py's
LET_GO_VARS): a death calls the exit off.

Every Tick rather than once at the ask: a probe starts the countdown by
writing its variables, and the freeze follows ExitPending either way.

The move and the trigger are the local player's alone (nothing stamps them
on another copy), as the countdown is: ExitPending is written by AskSaveExit
on the copy the HUD asked, and nothing replicates it.
"""

from uebp.graph import _connect, _loose_pin, _palette, _pin, out, then
from uebp.g import _G
from uebp.net import custom_event
from combat.ask_consts import (
    ASK_SAVE_EXIT, EXIT_AT_VAR, EXIT_CALLED_OFF_VAR, EXIT_DUE_VAR, EXIT_PENDING_VAR,
    EXIT_SECONDS, EXIT_STARTED_VAR,
)
from combat.game_state import LAST_DAMAGE_VAR
from combat.paths import HEALTH_CLASS_PATH
from combat.weapon_component.dead import OWNER_DEAD_VAR
from uebp.nodes.actor import (
    FN_GET_COMP, FN_GET_OWNER, FN_LAST_MOVE_INPUT, FN_ON_GROUND,
)
from uebp.nodes.math import FN_ADD_FF, FN_GE_FF, FN_GREATER_FF, FN_NOT, FN_OR, FN_VSIZE
from uebp.nodes.palette import NODE_CAST_HEALTH, NODE_CAST_PAWN
from uebp.nodes.system import FN_TIME_SECONDS

MOVEMENT_CLASS_PATH = "/Script/Engine.CharacterMovementComponent"


def author_ask_save_exit(ed):
    """The event (see the module docstring)."""
    g = _G(ed)
    event = g.keep(custom_event(ed, ASK_SAVE_EXIT))
    busy = g.call(FN_OR, A=g.get(EXIT_PENDING_VAR), B=g.get(OWNER_DEAD_VAR))
    _, start = g.branch(out(busy), [then(event)])
    now = out(g.call(FN_TIME_SECONDS))
    flow = g.put(EXIT_PENDING_VAR, "true", [start])
    flow = g.put(EXIT_STARTED_VAR, now, [flow])
    flow = g.put(EXIT_AT_VAR, out(g.call(FN_ADD_FF, A=now, B=str(EXIT_SECONDS))), [flow])
    g.put(EXIT_DUE_VAR, "false", [flow])
    ed.add_comment_to_nodes(
        f"{ASK_SAVE_EXIT}: the M panel's save-and-exit row. With no exit running it "
        f"starts the {EXIT_SECONDS:.0f} s countdown (save_exit.py).", g.made)


def _author_save_exit(ed, in_execs, tap):
    """The running countdown (see the module docstring); ``tap`` is the
    Tick's trigger pin (trigger.py's, made once). Returns the exits."""
    g = _G(ed)
    running, idle = g.branch(g.get(EXIT_PENDING_VAR), in_execs)
    owner = out(g.call(FN_GET_OWNER))
    now = out(g.call(FN_TIME_SECONDS))
    comp = g.call(FN_GET_COMP, self=owner)
    _pin(comp, "ComponentClass").set_pin_value(HEALTH_CLASS_PATH)
    cast = g.keep(_palette(ed, NODE_CAST_HEALTH))
    _connect(out(comp), _pin(cast, "Object"))
    _connect(running, _pin(cast, "execute"))
    health = _loose_pin(cast, "AsBPHealthComponent", is_input=False)
    struck = g.iget(health, LAST_DAMAGE_VAR, HEALTH_CLASS_PATH)
    since = g.call(FN_GREATER_FF, A=struck, B=g.get(EXIT_STARTED_VAR))

    # The owner as a pawn, for its move keys: the last movement input it took.
    as_pawn = g.keep(_palette(ed, NODE_CAST_PAWN))
    _connect(owner, _pin(as_pawn, "Object"))
    _connect(then(cast), _pin(as_pawn, "execute"))
    pawn = _loose_pin(as_pawn, "AsPawn", is_input=False)
    input_size = g.call(FN_VSIZE, A=out(g.call(FN_LAST_MOVE_INPUT, self=pawn)))
    moved = g.call(FN_GREATER_FF, A=out(input_size), B="0.0")
    # Off the ground: the movement is the walking mode's no longer.
    moves = g.call(FN_GET_COMP, self=owner)
    _pin(moves, "ComponentClass").set_pin_value(MOVEMENT_CLASS_PATH)
    aloft = g.call(FN_NOT, A=out(g.call(FN_ON_GROUND, self=out(moves))))
    acted = g.call(FN_OR, A=out(g.call(FN_OR, A=out(since), B=out(moved))), B=tap)
    off_by = g.call(FN_OR, A=out(acted), B=out(aloft))
    hit, unhurt = g.branch(out(off_by), [then(as_pawn)])

    off = g.put(EXIT_PENDING_VAR, "false", [hit])
    off = g.put(EXIT_CALLED_OFF_VAR, now, [off])

    ripe = g.call(FN_GE_FF, A=now, B=g.get(EXIT_AT_VAR))
    leave, wait = g.branch(out(ripe), [unhurt, out(cast, "CastFailed"),
                                        out(as_pawn, "CastFailed")])
    due = g.put(EXIT_PENDING_VAR, "false", [leave])
    due = g.put(EXIT_DUE_VAR, "true", [due])
    ed.add_comment_to_nodes(
        "Save and exit, counting down: a hit since the start, a move key, the "
        "trigger or leaving the ground calls it off; the time up, ExitDue says "
        "the character may be saved and the player leave. The movement is never "
        "disabled: the feet stay fitted to the ground (save_exit.py).", g.made)
    return [off, wait, due, idle]
