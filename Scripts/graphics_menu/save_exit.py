"""Save and exit, loading the profile, and losing it on death: the HUD's Tick.

One fragment, run every Tick after the grass sync, in this order:

  1. Dead (Health <= 0)?  Delete the profile slot, once, and call off any
     exit. Tick, not DrawHUD: the player's death pauses the game only after
     its 2.2 s settle, so Tick sees Health reach zero, and a -nullrhi run --
     which never draws -- can be probed.
  2. A started game whose profile has not been looked for, with the loadout
     spawned?  ProfileChecked = true; if the slot exists, profile_read.py.
  3. X with the M panel open, and no exit running?  ExitPending, ExitStartedAt
     = now, ExitAt = now + EXIT_SECONDS, and the panel closes.
  4. An exit running?  If the player was hit since it started
     (BP_HealthComponent.LastDamageTime, stamped by the wanderers' swing) it
     is called off and the pawn walks again; once ExitAt has passed,
     profile_write.py and the current level is reopened -- which opens on the
     main menu. Until then the pawn's CharacterMovement is disabled, every
     Tick, so the character stands still for the whole countdown. Every Tick
     rather than once at the X: the countdown can be started by writing its
     variables (the probe does), and the freeze follows ExitPending either way.
  5. The dev-all-guns cheat ([K] in the panel; dev_guns.py).

Everything reads off the player_parts cast chain; a pawn without the parts
skips the whole fragment.
"""

from combat.graph import BEL, _at, _connect, _node, _pin, _set
from combat.paths import HEALTH_CLASS_PATH, WEAPON_COMP_CLASS_PATH
from graphics_menu.menu_nav import or_pause_click
from graphics_menu.dev_guns import author_dev_guns
from graphics_menu.player_parts import PAWN, author_player_parts
from graphics_menu.profile_consts import (
    EXIT_AT_VAR, EXIT_CALLED_OFF_VAR, EXIT_KEY, EXIT_PENDING_VAR, EXIT_SECONDS,
    EXIT_STARTED_VAR, NEVER, PROFILE_CHECKED_VAR, PROFILE_FORGOTTEN_VAR,
    PROFILE_SLOT, PROFILE_USER_INDEX,
)
from graphics_menu.profile_read import author_read_profile
from graphics_menu.profile_write import author_write_profile

FN_LE = "/Script/Engine.KismetMathLibrary.LessEqual_DoubleDouble"
FN_GREATER = "/Script/Engine.KismetMathLibrary.Greater_DoubleDouble"
FN_GE = "/Script/Engine.KismetMathLibrary.GreaterEqual_DoubleDouble"
FN_ADD = "/Script/Engine.KismetMathLibrary.Add_DoubleDouble"
FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_NOT = "/Script/Engine.KismetMathLibrary.Not_PreBool"
FN_GREATER_II = "/Script/Engine.KismetMathLibrary.Greater_IntInt"
FN_ARR_LEN = "/Script/Engine.KismetArrayLibrary.Array_Length"
FN_TIME_SECONDS = "/Script/Engine.GameplayStatics.GetTimeSeconds"
FN_WAS_PRESSED = "/Script/Engine.PlayerController.WasInputKeyJustPressed"
FN_SAVE_EXISTS = "/Script/Engine.GameplayStatics.DoesSaveGameExist"
FN_DELETE_SAVE = "/Script/Engine.GameplayStatics.DeleteGameInSlot"
FN_LEVEL_NAME = "/Script/Engine.GameplayStatics.GetCurrentLevelName"
FN_OPEN_LEVEL = "/Script/Engine.GameplayStatics.OpenLevel"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_DISABLE_MOVEMENT = "/Script/Engine.CharacterMovementComponent.DisableMovement"
FN_SET_MOVEMENT_MODE = "/Script/Engine.CharacterMovementComponent.SetMovementMode"
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
        return [BEL.find_then_pin(node)]
    return list(in_execs)


def _setter(ed, var, value, in_execs, x, y, made):
    """Set a HUD variable to a literal (or, if ``value`` is a pin, to it)."""
    n = _at(ed.add_set_member_variable_node(var), x, y)
    if isinstance(value, str):
        _set(n, var, value)
    else:
        _connect(value, _pin(n, var))
    for e in in_execs:
        _connect(e, _pin(n, "execute"))
    made.append(n)
    return [BEL.find_then_pin(n)]


def _get(ed, var, x, y, made, owner=None, self_out=None):
    n = _at(ed.add_get_member_variable_node(var, owner) if owner
            else ed.add_get_member_variable_node(var), x, y)
    if self_out is not None:
        _connect(self_out, _pin(n, "self"))
    made.append(n)
    return _pin(n, var, is_input=False)


def _call(ed, fn, x, y, made, **inputs):
    """A math/test node with its inputs wired (pins) or set (literals)."""
    n = _at(_node(ed, fn), x, y)
    for name, v in inputs.items():
        if isinstance(v, (str, int, float)):
            _set(n, name, v)
        else:
            _connect(v, _pin(n, name))
    made.append(n)
    return n


def _out(n):
    return _pin(n, "ReturnValue", is_input=False)


def _branch(ed, cond, in_execs, x, y, made):
    br = _at(ed.add_branch_node(), x, y)
    _connect(cond, _pin(br, "Condition"))
    for e in in_execs:
        _connect(e, _pin(br, "execute"))
    made.append(br)
    return BEL.find_then_pin(br), BEL.find_else_pin(br)


def _author_forget_on_death(ed, health, in_execs, x0, y0, made):
    """Returns (alive exec, [tails of the dead arm])."""
    hp = _get(ed, "Health", x0, y0 + 300, made, HEALTH_CLASS_PATH, health)
    dead, alive = _branch(ed, _out(_call(ed, FN_LE, x0 + 240, y0 + 300, made,
                                         A=hp, B=0.0)),
                          in_execs, x0 + 480, y0, made)
    done, fresh = _branch(ed, _get(ed, PROFILE_FORGOTTEN_VAR, x0 + 480, y0 + 300, made),
                          [dead], x0 + 740, y0, made)
    wipe = _call(ed, FN_DELETE_SAVE, x0 + 1000, y0, made,
                 SlotName=PROFILE_SLOT, UserIndex=PROFILE_USER_INDEX)
    flow = _chain(wipe, [fresh])
    flow = _setter(ed, PROFILE_FORGOTTEN_VAR, "true", flow, x0 + 1260, y0, made)
    flow = _setter(ed, EXIT_PENDING_VAR, "false", flow, x0 + 1520, y0, made)
    return alive, flow + [done]


def _author_load_once(ed, parts, in_execs, x0, y0, made):
    """Returns the exec pins that continue, loaded or not."""
    started = _get(ed, "GameStarted", x0, y0 + 300, made)
    unchecked = _call(ed, FN_NOT, x0, y0 + 440, made,
                      A=_get(ed, PROFILE_CHECKED_VAR, x0 - 240, y0 + 440, made))
    due = _call(ed, FN_AND, x0 + 240, y0 + 300, made, A=started, B=_out(unchecked))
    look, skip = _branch(ed, _out(due), in_execs, x0 + 480, y0, made)

    # Only once the weapon component has spawned the issued loadout, or the
    # saved items would be added and the issued ones after them.
    inv = _get(ed, "Inventory", x0 + 480, y0 + 300, made, WEAPON_COMP_CLASS_PATH,
               parts[WEAPON_COMP_CLASS_PATH])
    count = _call(ed, FN_ARR_LEN, x0 + 720, y0 + 300, made, TargetArray=inv)
    armed = _call(ed, FN_GREATER_II, x0 + 960, y0 + 300, made, A=_out(count), B=0)
    ready, not_yet = _branch(ed, _out(armed), [look], x0 + 1200, y0, made)
    flow = _setter(ed, PROFILE_CHECKED_VAR, "true", [ready], x0 + 1460, y0, made)

    exists = _call(ed, FN_SAVE_EXISTS, x0 + 1720, y0 + 300, made,
                   SlotName=PROFILE_SLOT, UserIndex=PROFILE_USER_INDEX)
    flow = _chain(exists, flow)
    have, none = _branch(ed, _out(exists), flow, x0 + 1980, y0, made)
    loaded = author_read_profile(ed, have, parts, x0 + 2240, y0, made)
    return loaded + [none, not_yet, skip]


def _author_start(ed, pc_out, now_out, in_execs, x0, y0, made):
    """X in the open panel, with no exit running, starts the countdown."""
    pressed = _call(ed, FN_WAS_PRESSED, x0, y0 + 300, made, self=pc_out, Key=EXIT_KEY)
    in_menu = _call(ed, FN_AND, x0 + 240, y0 + 300, made,
                    A=_get(ed, "MenuOpen", x0, y0 + 440, made), B=_out(pressed))
    idle = _call(ed, FN_NOT, x0 + 240, y0 + 440, made,
                 A=_get(ed, EXIT_PENDING_VAR, x0, y0 + 580, made))
    asked = or_pause_click(ed, _out(in_menu), EXIT_KEY, x0, y0 + 760, made)
    go = _call(ed, FN_AND, x0 + 480, y0 + 300, made, A=asked, B=_out(idle))
    start, stay = _branch(ed, _out(go), in_execs, x0 + 720, y0, made)
    flow = _setter(ed, EXIT_PENDING_VAR, "true", [start], x0 + 980, y0, made)
    flow = _setter(ed, EXIT_STARTED_VAR, now_out, flow, x0 + 1240, y0, made)
    deadline = _call(ed, FN_ADD, x0 + 1240, y0 + 300, made, A=now_out, B=EXIT_SECONDS)
    flow = _setter(ed, EXIT_AT_VAR, _out(deadline), flow, x0 + 1500, y0, made)
    flow = _setter(ed, "MenuOpen", "false", flow, x0 + 1760, y0, made)
    return flow + [stay]


def _movement_call(ed, moves, fn, in_execs, x, y, made):
    """``fn`` on the pawn's CharacterMovement; returns (node, what follows)."""
    call = _call(ed, fn, x, y, made, self=moves)
    return call, _chain(call, in_execs)


def _author_countdown(ed, parts, now_out, in_execs, x0, y0, made):
    """A running exit: called off by a hit, or saved and left when it is due."""
    running, idle = _branch(ed, _get(ed, EXIT_PENDING_VAR, x0, y0 + 300, made),
                            in_execs, x0 + 240, y0, made)
    struck = _get(ed, "LastDamageTime", x0 + 240, y0 + 300, made, HEALTH_CLASS_PATH,
                  parts[HEALTH_CLASS_PATH])
    since = _call(ed, FN_GREATER, x0 + 480, y0 + 300, made, A=struck,
                  B=_get(ed, EXIT_STARTED_VAR, x0 + 240, y0 + 440, made))
    hit, unhurt = _branch(ed, _out(since), [running], x0 + 720, y0, made)
    off = _setter(ed, EXIT_PENDING_VAR, "false", [hit], x0 + 980, y0 - 300, made)
    off = _setter(ed, EXIT_CALLED_OFF_VAR, now_out, off, x0 + 1240, y0 - 300, made)
    comp = _call(ed, FN_GET_COMP, x0 + 1240, y0 + 600, made, self=parts[PAWN])
    _pin(comp, "ComponentClass").set_pin_value(MOVEMENT_CLASS_PATH)
    moves = _out(comp)
    walk, off = _movement_call(ed, moves, FN_SET_MOVEMENT_MODE, off,
                               x0 + 1500, y0 - 600, made)
    _set(walk, "NewMovementMode", "MOVE_Walking")

    ripe = _call(ed, FN_GE, x0 + 980, y0 + 300, made, A=now_out,
                 B=_get(ed, EXIT_AT_VAR, x0 + 740, y0 + 440, made))
    leave, wait = _branch(ed, _out(ripe), [unhurt], x0 + 1240, y0, made)
    # Standing still while the countdown runs; the reopened level brings a
    # fresh pawn, so only the hit arm has to give the movement back.
    _, wait = _movement_call(ed, moves, FN_DISABLE_MOVEMENT, [wait],
                             x0 + 1500, y0 + 600, made)
    flow = _setter(ed, EXIT_PENDING_VAR, "false", [leave], x0 + 1500, y0, made)
    written = author_write_profile(ed, flow[0], parts, x0 + 1760, y0, made)

    # The current map by name, so the exit reopens whatever level is loaded,
    # and a reopened level opens on the main menu (GameStarted is false again).
    where = _call(ed, FN_LEVEL_NAME, x0 + 6800, y0, made, bRemovePrefixString="true")
    flow = _chain(where, written)
    reopen = _call(ed, FN_OPEN_LEVEL, x0 + 7060, y0, made, LevelName=_out(where))
    _chain(reopen, flow)
    return off + wait + [idle]


def author_save_exit_tick(ed, pc_out, in_execs, x0, y0):
    """The whole fragment (see the module docstring). Returns the tails."""
    made = []
    ok, fails, parts = author_player_parts(ed, in_execs, x0, y0 - 600, made)
    now_out = _out(_call(ed, FN_TIME_SECONDS, x0, y0 + 900, made))
    alive, dead_tails = _author_forget_on_death(ed, parts[HEALTH_CLASS_PATH],
                                                [ok], x0 + 2400, y0, made)
    flow = _author_load_once(ed, parts, [alive], x0 + 4400, y0, made)
    flow = _author_start(ed, pc_out, now_out, flow, x0 + 12000, y0, made)
    flow = _author_countdown(ed, parts, now_out, flow, x0 + 14000, y0, made)
    flow = author_dev_guns(ed, pc_out, parts, flow, x0 + 22000, y0, made)
    ed.add_comment_to_nodes(
        f"Save and exit ([{EXIT_KEY}] in the panel, {EXIT_SECONDS:.0f} s, called off "
        f"by a hit), the saved profile loaded once a game starts, and deleted "
        f"when the player dies.", made[:1])
    return flow + dead_tails + fails
