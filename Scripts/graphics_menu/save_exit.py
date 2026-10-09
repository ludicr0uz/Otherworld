"""Save and exit, loading the profile, and losing it on death: the HUD's Tick.

One fragment, run every Tick after the grass sync, in this order:

  1. Dead (Health <= 0)?  Delete the profile slot, once. (The weapon
     component's dead gate calls off any exit.) Tick, not DrawHUD: the
     player's death pauses the game only after its 2.2 s settle, so Tick sees
     Health reach zero, and a -nullrhi run -- which never draws -- can be
     probed.
  2. A started game whose profile has not been looked for, with the loadout
     spawned?  ProfileChecked = true; if the slot exists, profile_read.py.
  3. The panel's save-and-exit row taken, no exit running?  The weapon
     component is asked (AskSaveExit, ask.py), and the panel closes.
  4. The component's ExitDue, not yet left?  ExitLeaving, profile_write.py,
     and the current level is reopened -- which opens on the main menu.

The countdown itself is the character's, not the screen's: the weapon
component runs it (combat/weapon_component/save_exit.py: the 15 s, standing
still, a hit calling it off) and says ExitDue when it is over. This fragment
asks, and leaves; the banner (profile_draw.py) reads the component's clock.
  5. The dev-all-guns cheat (its row in the panel; dev_guns.py).

Everything reads off the player_parts cast chain; a pawn without the parts
skips the whole fragment.
"""

from uebp.vars import declare, defaults
from graphics_menu.profile_consts import HUD_TABLE
from uebp.graph import BEL, _connect, _node, _pin, _set, else_, out, then
from combat.ask_consts import ASK_SAVE_EXIT, EXIT_DUE_VAR, EXIT_PENDING_VAR, EXIT_SECONDS
from combat.paths import HEALTH_CLASS_PATH, WEAPON_COMP_CLASS_PATH
from graphics_menu.ask import ask
from graphics_menu.menu_nav import pause_row_taken
from graphics_menu.dev_guns import author_dev_guns
from graphics_menu.player_parts import author_player_parts
from graphics_menu.profile_consts import (
    EXIT_ACTION, EXIT_LEAVING_VAR, PROFILE_CHECKED_VAR, PROFILE_FORGOTTEN_VAR,
    PROFILE_SLOT, PROFILE_USER_INDEX,
)
from graphics_menu.profile_read import author_read_profile
from graphics_menu.profile_write import author_write_profile
from uebp.nodes.array import FN_ARR_LEN
from uebp.nodes.math import FN_AND, FN_GREATER_II, FN_LE_FF, FN_NOT
from uebp.nodes.system import FN_DELETE_SAVE, FN_LEVEL_NAME, FN_OPEN_LEVEL, FN_SAVE_EXISTS
from graphics_menu.umg_consts import GAME_STARTED_VAR
from combat import health_vars as HV
from graphics_menu import hud_vars as MV
from combat.weapon_component import vars as WV

# The countdown's, which the HUD held before the weapon component did.
RETIRED_VARS = ("ExitPending", "ExitAt", "ExitStartedAt", "ExitCalledOffAt")


def declare_profile_vars(ed):
    """The HUD's profile flags. Defaults: profile_defaults()."""
    for name in RETIRED_VARS:
        ed.remove_member_variable(name)
    declare(ed, HUD_TABLE)


def profile_defaults():
    return defaults(HUD_TABLE)


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
    hp = _get(ed, HV.Health, made, HEALTH_CLASS_PATH, health)
    dead, alive = _branch(ed, out(_call(ed, FN_LE_FF, made, A=hp, B=0.0)), in_execs, made)
    done, fresh = _branch(ed, _get(ed, PROFILE_FORGOTTEN_VAR, made), [dead], made)
    wipe = _call(ed, FN_DELETE_SAVE, made, SlotName=PROFILE_SLOT, UserIndex=PROFILE_USER_INDEX)
    flow = _chain(wipe, [fresh])
    flow = _setter(ed, PROFILE_FORGOTTEN_VAR, "true", flow, made)
    return alive, flow + [done]


def _author_load_once(ed, parts, in_execs, made):
    """Returns the exec pins that continue, loaded or not."""
    started = _get(ed, GAME_STARTED_VAR, made)
    unchecked = _call(ed, FN_NOT, made, A=_get(ed, PROFILE_CHECKED_VAR, made))
    due = _call(ed, FN_AND, made, A=started, B=out(unchecked))
    look, skip = _branch(ed, out(due), in_execs, made)

    # Only once the weapon component has spawned the issued loadout, or the
    # saved items would be added and the issued ones after them.
    inv = _get(ed, WV.Inventory, made, WEAPON_COMP_CLASS_PATH, parts[WEAPON_COMP_CLASS_PATH])
    count = _call(ed, FN_ARR_LEN, made, TargetArray=inv)
    armed = _call(ed, FN_GREATER_II, made, A=out(count), B=0)
    ready, not_yet = _branch(ed, out(armed), [look], made)
    flow = _setter(ed, PROFILE_CHECKED_VAR, "true", [ready], made)

    exists = _call(ed, FN_SAVE_EXISTS, made, SlotName=PROFILE_SLOT, UserIndex=PROFILE_USER_INDEX)
    flow = _chain(exists, flow)
    have, none = _branch(ed, out(exists), flow, made)
    loaded = author_read_profile(ed, have, parts, made)
    return loaded + [none, not_yet, skip]


def _author_start(ed, wc, in_execs, made):
    """The M panel's save-and-exit row, with no exit running, asks the weapon
    component for the countdown, and the panel closes."""
    idle = _call(ed, FN_NOT, made, A=_get(ed, EXIT_PENDING_VAR, made, WEAPON_COMP_CLASS_PATH, wc))
    asked = pause_row_taken(ed, EXIT_ACTION, made)
    go = _call(ed, FN_AND, made, A=asked, B=out(idle))
    start, stay = _branch(ed, out(go), in_execs, made)
    flow = [ask(ed, wc, ASK_SAVE_EXIT, [start], made)]
    flow = _setter(ed, MV.MenuOpen, "false", flow, made)
    return flow + [stay]


def _author_leave(ed, parts, in_execs, made):
    """The countdown over (the component's ExitDue): the profile is written
    and the level reopened, once."""
    due = _get(ed, EXIT_DUE_VAR, made, WEAPON_COMP_CLASS_PATH, parts[WEAPON_COMP_CLASS_PATH])
    fresh = _call(ed, FN_NOT, made, A=_get(ed, EXIT_LEAVING_VAR, made))
    leave, stay = _branch(ed, out(_call(ed, FN_AND, made, A=due, B=out(fresh))),
                          in_execs, made)
    flow = _setter(ed, EXIT_LEAVING_VAR, "true", [leave], made)
    written = author_write_profile(ed, flow[0], parts, made)

    # The current map by name, so the exit reopens whatever level is loaded,
    # and a reopened level opens on the main menu (GameStarted is false again).
    where = _call(ed, FN_LEVEL_NAME, made, bRemovePrefixString="true")
    flow = _chain(where, written)
    reopen = _call(ed, FN_OPEN_LEVEL, made, LevelName=out(where))
    _chain(reopen, flow)
    return [stay]


def author_save_exit_tick(ed, pc_out, in_execs):
    """The whole fragment (see the module docstring). Returns the tails."""
    made = []
    ok, fails, parts = author_player_parts(ed, in_execs, made)
    alive, dead_tails = _author_forget_on_death(ed, parts[HEALTH_CLASS_PATH], [ok], made)
    flow = _author_load_once(ed, parts, [alive], made)
    flow = _author_start(ed, parts[WEAPON_COMP_CLASS_PATH], flow, made)
    flow = _author_leave(ed, parts, flow, made)
    flow = author_dev_guns(ed, pc_out, parts, flow, made)
    ed.add_comment_to_nodes(
        f"Save and exit (its row in the M panel, {EXIT_SECONDS:.0f} s, called off "
        f"by a hit), the saved profile loaded once a game starts, and deleted "
        f"when the player dies.", made[:1])
    return flow + dead_tails + fails
