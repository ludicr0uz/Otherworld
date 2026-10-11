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
        (the trigger's tap, trigger.py; a probe's FireForced too)
            -> called off: ExitPending = false, ExitCalledOffAt = now, and
               the owner walks again
        ExitAt passed -> ExitPending = false, ExitDue = true
        else the owner's CharacterMovement is disabled, every Tick, so the
            character stands still for the whole countdown

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

from uebp.graph import _connect, _loose_pin, _palette, _pin, _set, out, then
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
    FN_DISABLE_MOVEMENT, FN_GET_COMP, FN_GET_OWNER, FN_LAST_MOVE_INPUT, FN_SET_MOVEMENT_MODE,
)
from uebp.nodes.math import FN_ADD_FF, FN_GE_FF, FN_GREATER_FF, FN_OR, FN_VSIZE
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
    off_by = g.call(FN_OR, A=out(g.call(FN_OR, A=out(since), B=out(moved))), B=tap)
    hit, unhurt = g.branch(out(off_by), [then(as_pawn)])

    moves = g.call(FN_GET_COMP, self=owner)
    _pin(moves, "ComponentClass").set_pin_value(MOVEMENT_CLASS_PATH)
    off = g.put(EXIT_PENDING_VAR, "false", [hit])
    off = g.put(EXIT_CALLED_OFF_VAR, now, [off])
    walk = g.call(FN_SET_MOVEMENT_MODE, [off], self=out(moves))
    _set(walk, "NewMovementMode", "MOVE_Walking")

    ripe = g.call(FN_GE_FF, A=now, B=g.get(EXIT_AT_VAR))
    leave, wait = g.branch(out(ripe), [unhurt, out(cast, "CastFailed"),
                                        out(as_pawn, "CastFailed")])
    # Standing still while the countdown runs; leaving brings a fresh pawn, so
    # only the called-off arm has to give the movement back.
    still = g.call(FN_DISABLE_MOVEMENT, [wait], self=out(moves))
    due = g.put(EXIT_PENDING_VAR, "false", [leave])
    due = g.put(EXIT_DUE_VAR, "true", [due])
    ed.add_comment_to_nodes(
        "Save and exit, counting down: the owner stands still; a hit since the "
        "start, a move key or the trigger calls it off and they walk again; the "
        "time up, ExitDue says the character may be saved and the player leave "
        "(save_exit.py).", g.made)
    return [then(walk), then(still), due, idle]
