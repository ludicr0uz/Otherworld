"""BP_Settings: the SaveGame the graphics menu and the weapon component
both read, so rebinds and sensitivity survive a restart.
"""

import unreal

from combat.graph import (
    BEL, BGE, _apply_defaults, _create_blueprint, _declare, _float_type, _key,
    _log, _struct_type,
)
from combat.paths import SETTINGS_BP_PATH, SETTINGS_SLOT
from combat.tuning import BIND_VARS, COMBAT


def build_settings_savegame(rebuild=True):
    """The settings the player keeps between runs: BP_Settings, a USaveGame.

    A SaveGame and not a GameInstance, and built HERE and not in
    build_graphics_menu.py, for the same reason: both of its consumers have to
    be able to name the class. The HUD loads it, edits it and saves it; the
    weapon component is handed the values every frame and never touches the
    disk. Putting it in the HUD's builder would mean the HUD's builder had to
    run first, and putting it on a GameInstance would mean the menu could not
    write to it without the game already being in progress.

    No graph: this is a record, not behaviour.
    """
    bp = _create_blueprint(SETTINGS_BP_PATH, unreal.SaveGame)
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    _declare(ed, "MouseSensitivity", _float_type())
    # Indexed, not a struct per bind and not seven separate variables: the
    # settings screen walks the rows with one ForEachLoop and one Array_Set, and
    # BIND_VARS is what says which index means which action.
    _declare(ed, "Binds", BEL.get_array_type(_struct_type(unreal.Key.static_struct())))
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_Settings failed to compile")
    _apply_defaults(bp, {
        "MouseSensitivity": COMBAT.mouse_sensitivity_default,
        "Binds": [_key(k) for _name, k in BIND_VARS],
    })
    _log(f"built {SETTINGS_BP_PATH} (slot {SETTINGS_SLOT!r})")
    return bp
