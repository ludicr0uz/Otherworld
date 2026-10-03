"""Save and exit, loading the profile, and losing it on death: the HUD's Tick.

One fragment, run every Tick after the grass sync, in this order:

  1. Dead (Health <= 0)?  Delete the profile slot, once, and call off any
     exit. Tick, not DrawHUD: the player's death pauses the game only after
     its 2.2 s settle, so Tick sees Health reach zero, and a -nullrhi run --
     which never draws -- can be probed.
  2. A started game whose profile has not been looked for, with the loadout
     spawned?  ProfileChecked = true; if the slot exists, profile_read.py.
  3. The panel's save-and-exit row taken, no exit running?  ExitPending, ExitStartedAt
     = now, ExitAt = now + EXIT_SECONDS, and the panel closes.
  4. An exit running?  If the player was hit since it started
     (BP_HealthComponent.LastDamageTime, stamped by the wanderers' swing) it
     is called off and the pawn walks again; once ExitAt has passed,
     profile_write.py and the current level is reopened -- which opens on the
     main menu. Until then the pawn's CharacterMovement is disabled, every
     Tick, so the character stands still for the whole countdown. Every Tick
     rather than once at the X: the countdown can be started by writing its
     variables (the probe does), and the freeze follows ExitPending either way.
  5. The dev-all-guns cheat (its row in the panel; dev_guns.py).

Everything reads off the player_parts cast chain; a pawn without the parts
skips the whole fragment.
"""

from uebp.graph import BEL, _connect, _node, _pin, _set, else_, out, then
from combat.paths import HEALTH_CLASS_PATH, WEAPON_COMP_CLASS_PATH
from graphics_menu.menu_nav import pause_row_taken
from graphics_menu.dev_guns import author_dev_guns
from graphics_menu.player_parts import PAWN, author_player_parts
from graphics_menu.profile_consts import (
    EXIT_AT_VAR, EXIT_CALLED_OFF_VAR, EXIT_ACTION, EXIT_PENDING_VAR, EXIT_SECONDS,
    EXIT_STARTED_VAR, NEVER, PROFILE_CHECKED_VAR, PROFILE_FORGOTTEN_VAR,
    PROFILE_SLOT, PROFILE_USER_INDEX,
)
from graphics_menu.profile_read import author_read_profile
from graphics_menu.profile_write import author_write_profile
from uebp.nodes.actor import FN_DISABLE_MOVEMENT, FN_GET_COMP, FN_SET_MOVEMENT_MODE
from uebp.nodes.array import FN_ARR_LEN
from uebp.nodes.math import (
    FN_ADD_FF, FN_AND, FN_GE_FF, FN_GREATER_FF, FN_GREATER_II, FN_LE_FF, FN_NOT)
from uebp.nodes.system import (
    FN_DELETE_SAVE, FN_LEVEL_NAME, FN_OPEN_LEVEL, FN_SAVE_EXISTS, FN_TIME_SECONDS)

MOVEMENT_CLASS_PATH = "/Script/Engine.CharacterMovementComponent"

_BOOLS = (EXIT_PENDING_VAR, PROFILE_CHECKED_VAR, PROFILE_FORGOTTEN_VAR)
_REALS = (EXIT_AT_VAR, EXIT_STARTED_VAR, EXIT_CALLED_OFF_VAR)


def declare_profile_vars(ed):
    """The HUD's countdown and profile flags. Defaults: profile_defaults()."""
    for name in _BOOLS + _REALS:
        kind = "bool" if name in _BOOLS else "real"
        ed.remove_member_variable(name)
        if not ed.add_member_variable(name, BEL.get_basic_type_by_name(kind)):
            raise RuntimeError(f"could not declare member variable {name}")


def profile_defaults():
    return {**{n: False for n in _BOOLS}, EXIT_AT_VAR: 0.0,
            EXIT_STARTED_VAR: NEVER, EXIT_CALLED_OFF_VAR: NEVER}


def _chain(node, in_execs):
    """Wire the execs in if the node has an exec pin (DoesSaveGameExist and
    friends may be pure); return what follows."""
    pin = BEL.find_input_pin(node, "execute")
    if pin and pin.is_valid():
        for e in in_execs:
            _connect(e, pin)
        return [then(node)]
    return list(in_execs)


def _setter(ed, var, value, in_execs, made):
    """Set a HUD variable to a literal (or, if ``value`` is a pin, to it)."""
    n = ed.add_set_member_variable_node(var)
    if isinstance(value, str):
        _set(n, var, value)
    else:
        _connect(value, _pin(n, var))
    for e in in_execs:
        _connect(e, _pin(n, "execute"))
    made.append(n)
    return [then(n)]


def _get(ed, var, made, owner=None, self_out=None):
    n = (ed.add_get_member_variable_node(var, owner) if owner
            else ed.add_get_member_variable_node(var))
    if self_out is not None:
        _connect(self_out, _pin(n, "self"))
    made.append(n)
    return out(n, var)


def _call(ed, fn, made, **inputs):
    """A math/test node with its inputs wired (pins) or set (literals)."""
    n = _node(ed, fn)
    for name, v in inputs.items():
        if isinstance(v, (str, int, float)):
            _set(n, name, v)
        else:
            _connect(v, _pin(n, name))
    made.append(n)
    return n


def _branch(ed, cond, in_execs, made):
    br = ed.add_branch_node()
    _connect(cond, _pin(br, "Condition"))
    for e in in_execs:
        _connect(e, _pin(br, "execute"))
    made.append(br)
    return then(br), else_(br)


def _author_forget_on_death(ed, health, in_execs, made):
    """Returns (alive exec, [tails of the dead arm])."""
    hp = _get(ed, "Health", made, HEALTH_CLASS_PATH, health)
    dead, alive = _branch(ed, out(_call(ed, FN_LE_FF, made, A=hp, B=0.0)), in_execs, made)
    done, fresh = _branch(ed, _get(ed, PROFILE_FORGOTTEN_VAR, made), [dead], made)
    wipe = _call(ed, FN_DELETE_SAVE, made, SlotName=PROFILE_SLOT, UserIndex=PROFILE_USER_INDEX)
    flow = _chain(wipe, [fresh])
    flow = _setter(ed, PROFILE_FORGOTTEN_VAR, "true", flow, made)
    flow = _setter(ed, EXIT_PENDING_VAR, "false", flow, made)
    return alive, flow + [done]


def _author_load_once(ed, parts, in_execs, made):
    """Returns the exec pins that continue, loaded or not."""
    started = _get(ed, "GameStarted", made)
    unchecked = _call(ed, FN_NOT, made, A=_get(ed, PROFILE_CHECKED_VAR, made))
    due = _call(ed, FN_AND, made, A=started, B=out(unchecked))
    look, skip = _branch(ed, out(due), in_execs, made)

    # Only once the weapon component has spawned the issued loadout, or the
    # saved items would be added and the issued ones after them.
    inv = _get(ed, "Inventory", made, WEAPON_COMP_CLASS_PATH, parts[WEAPON_COMP_CLASS_PATH])
    count = _call(ed, FN_ARR_LEN, made, TargetArray=inv)
    armed = _call(ed, FN_GREATER_II, made, A=out(count), B=0)
    ready, not_yet = _branch(ed, out(armed), [look], made)
    flow = _setter(ed, PROFILE_CHECKED_VAR, "true", [ready], made)

    exists = _call(ed, FN_SAVE_EXISTS, made, SlotName=PROFILE_SLOT, UserIndex=PROFILE_USER_INDEX)
    flow = _chain(exists, flow)
    have, none = _branch(ed, out(exists), flow, made)
    loaded = author_read_profile(ed, have, parts, made)
    return loaded + [none, not_yet, skip]


def _author_start(ed, pc_out, now_out, in_execs, made):
    """The M panel's save-and-exit row, with no exit running, starts the
    countdown."""
    idle = _call(ed, FN_NOT, made, A=_get(ed, EXIT_PENDING_VAR, made))
    asked = pause_row_taken(ed, EXIT_ACTION, made)
    go = _call(ed, FN_AND, made, A=asked, B=out(idle))
    start, stay = _branch(ed, out(go), in_execs, made)
    flow = _setter(ed, EXIT_PENDING_VAR, "true", [start], made)
    flow = _setter(ed, EXIT_STARTED_VAR, now_out, flow, made)
    deadline = _call(ed, FN_ADD_FF, made, A=now_out, B=EXIT_SECONDS)
    flow = _setter(ed, EXIT_AT_VAR, out(deadline), flow, made)
    flow = _setter(ed, "MenuOpen", "false", flow, made)
    return flow + [stay]


def _movement_call(ed, moves, fn, in_execs, made):
    """``fn`` on the pawn's CharacterMovement; returns (node, what follows)."""
    call = _call(ed, fn, made, self=moves)
    return call, _chain(call, in_execs)


def _author_countdown(ed, parts, now_out, in_execs, made):
    """A running exit: called off by a hit, or saved and left when it is due."""
    running, idle = _branch(ed, _get(ed, EXIT_PENDING_VAR, made), in_execs, made)
    struck = _get(ed, "LastDamageTime", made, HEALTH_CLASS_PATH, parts[HEALTH_CLASS_PATH])
    since = _call(ed, FN_GREATER_FF, made, A=struck, B=_get(ed, EXIT_STARTED_VAR, made))
    hit, unhurt = _branch(ed, out(since), [running], made)
    off = _setter(ed, EXIT_PENDING_VAR, "false", [hit], made)
    off = _setter(ed, EXIT_CALLED_OFF_VAR, now_out, off, made)
    comp = _call(ed, FN_GET_COMP, made, self=parts[PAWN])
    _pin(comp, "ComponentClass").set_pin_value(MOVEMENT_CLASS_PATH)
    moves = out(comp)
    walk, off = _movement_call(ed, moves, FN_SET_MOVEMENT_MODE, off, made)
    _set(walk, "NewMovementMode", "MOVE_Walking")

    ripe = _call(ed, FN_GE_FF, made, A=now_out, B=_get(ed, EXIT_AT_VAR, made))
    leave, wait = _branch(ed, out(ripe), [unhurt], made)
    # Standing still while the countdown runs; the reopened level brings a
    # fresh pawn, so only the hit arm has to give the movement back.
    _, wait = _movement_call(ed, moves, FN_DISABLE_MOVEMENT, [wait], made)
    flow = _setter(ed, EXIT_PENDING_VAR, "false", [leave], made)
    written = author_write_profile(ed, flow[0], parts, made)

    # The current map by name, so the exit reopens whatever level is loaded,
    # and a reopened level opens on the main menu (GameStarted is false again).
    where = _call(ed, FN_LEVEL_NAME, made, bRemovePrefixString="true")
    flow = _chain(where, written)
    reopen = _call(ed, FN_OPEN_LEVEL, made, LevelName=out(where))
    _chain(reopen, flow)
    return off + wait + [idle]


def author_save_exit_tick(ed, pc_out, in_execs):
    """The whole fragment (see the module docstring). Returns the tails."""
    made = []
    ok, fails, parts = author_player_parts(ed, in_execs, made)
    now_out = out(_call(ed, FN_TIME_SECONDS, made))
    alive, dead_tails = _author_forget_on_death(ed, parts[HEALTH_CLASS_PATH], [ok], made)
    flow = _author_load_once(ed, parts, [alive], made)
    flow = _author_start(ed, pc_out, now_out, flow, made)
    flow = _author_countdown(ed, parts, now_out, flow, made)
    flow = author_dev_guns(ed, pc_out, parts, flow, made)
    ed.add_comment_to_nodes(
        f"Save and exit (its row in the M panel, {EXIT_SECONDS:.0f} s, called off "
        f"by a hit), the saved profile loaded once a game starts, and deleted "
        f"when the player dies.", made[:1])
    return flow + dead_tails + fails
