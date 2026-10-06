"""The HUD's reach to the session (the GameInstance, net/session_consts.py)
and to the saved server address (BP_Settings): the node shapes mode_draw.py
and mode_tick.py share.

Every use is behind the cast: a game whose GameInstance is not ours (the
asset missing, so the engine fell back to a plain one) has no session to
read, and carries on down the cast's failed pin.
"""

import unreal

from uebp.graph import _connect, _loose_pin, _palette, _pin, _set, out, then
from graphics_menu.dev_guns import _call, _get
from graphics_menu.settings_rows import SETTINGS_CLASS_PATH
from net.session_consts import (
    GAME_INSTANCE_BP_PATH, GAME_INSTANCE_CLASS_PATH, SERVER_ADDRESS_VAR)
from uebp.nodes.palette import NODE_CAST_GAME_INSTANCE
from uebp.nodes.system import FN_GET_GAME_INSTANCE
from graphics_menu import hud_vars as MV


def session(ed, in_execs, made):
    """The GameInstance as ours: ``(pin, then, cast failed)``."""
    unreal.load_asset(GAME_INSTANCE_BP_PATH)   # for its cast node
    cast = _palette(ed, NODE_CAST_GAME_INSTANCE)
    made.append(cast)
    _connect(out(_call(ed, FN_GET_GAME_INSTANCE, made)), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    return (_loose_pin(cast, "AsBPOtherworldGameInstance", is_input=False), then(cast),
            out(cast, "CastFailed"))


def sget(ed, gi, var, made):
    return _get(ed, var, made, GAME_INSTANCE_CLASS_PATH, gi)


def _put_on(ed, owner_class, owner, var, value, in_execs, made):
    n = ed.add_set_member_variable_node(var, owner_class)
    made.append(n)
    _connect(owner, _pin(n, "self"))
    if isinstance(value, (str, bool)):
        _set(n, var, value)
    else:
        _connect(value, _pin(n, var))
    for e in in_execs:
        _connect(e, _pin(n, "execute"))
    return then(n)


def sput(ed, gi, var, value, in_execs, made):
    """One of the session's variables := a literal or a pin. Returns then."""
    return _put_on(ed, GAME_INSTANCE_CLASS_PATH, gi, var, value, in_execs, made)


def settings(ed, made):
    return _get(ed, MV.Settings, made)


def address(ed, made):
    """The saved server address: a String pin."""
    return _get(ed, SERVER_ADDRESS_VAR, made, SETTINGS_CLASS_PATH, settings(ed, made))


def put_address(ed, value, in_execs, made):
    return _put_on(ed, SETTINGS_CLASS_PATH, settings(ed, made), SERVER_ADDRESS_VAR, value,
                   in_execs, made)
