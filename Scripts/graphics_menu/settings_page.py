"""The settings page: filling it in, and pushing what it holds onto
BP_WeaponComponent every frame. Its input half is settings_input.py; its
constants are settings_rows.py.
"""

from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, else_, out, then
from graphics_menu.difficulty import author_difficulty_name
from graphics_menu.settings_input import _author_capture
from graphics_menu.settings_rows import (
    BACK_ROW, BIND_VARS, DIFFICULTY_ROW, FIRST_BIND_ROW, SETTINGS_CLASS_PATH, SETTINGS_ROWS,
    SETTINGS_SLOT, SLIDERS)
from graphics_menu.ui_graph import mark_rows, member, part, row_value, set_shown
from graphics_menu.umg_consts import (
    HINT_CAPTURE, HINT_IDLE, ROW_CARET, SETTINGS_BACK, SETTINGS_ROWS_BOX, WBP_MAIN_MENU,
    WBP_MENU_ROW)
from uebp.nodes.actor import FN_GET_COMP, FN_GET_OWNING_PAWN
from uebp.nodes.array import FN_ARR_GET
from uebp.nodes.math import FN_ADD_II, FN_GE_II, FN_SELECT_FF
from uebp.nodes.palette import MACRO_FOR_EACH, NODE_CAST_WEAPON
from uebp.nodes.umg import FN_SET_OPACITY
from uebp.nodes.system import FN_FLOAT_TO_STR, FN_IS_VALID, FN_KEY_DISPLAY
from graphics_menu import hud_vars as MV
from combat import settings_vars as SV

WEAPON_COMP_CLASS_PATH = "/Game/Weapons/BP_WeaponComponent.BP_WeaponComponent_C"


def _author_push_settings(ed, in_execs):
    """Hand BP_WeaponComponent the player's settings, every DrawHUD frame.

    A push and not a pull, and that direction is the whole design. The
    component would otherwise have to load the save itself (a second reader of
    one file) or cast to the HUD (a component reaching for an actor that may
    not exist). Pushed, it keeps plain member variables with CDO defaults that
    already work on their own, and the settings screen is the only thing that
    knows a disk is involved.

    Written from DrawHUD rather than Tick for the same reason everything else
    here is: the menu is a paused world, and Tick does not run in one -- so a
    sensitivity changed on the settings screen has to land before the game is
    unpaused, not on the first frame after it.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    got = keep(ed.add_get_member_variable_node(MV.Settings))
    settings_out = out(got, MV.Settings)
    ok = keep(_node(ed, FN_IS_VALID))
    _connect(settings_out, _pin(ok, "Object"))
    have = keep(ed.add_branch_node())
    _connect(out(ok), _pin(have, "Condition"))
    for e in in_execs:
        _connect(e, _pin(have, "execute"))

    pawn = keep(_node(ed, FN_GET_OWNING_PAWN))
    comp = keep(_node(ed, FN_GET_COMP))
    _connect(out(pawn), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    cast = keep(_palette(ed, NODE_CAST_WEAPON))
    _connect(out(comp), _pin(cast, "Object"))
    _connect(then(have), _pin(cast, "execute"))
    as_weapon = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    flow = then(cast)
    for i, slider in enumerate(SLIDERS):
        value = keep(ed.add_get_member_variable_node(slider.var, SETTINGS_CLASS_PATH))
        _connect(settings_out, _pin(value, "self"))
        push = keep(ed.add_set_member_variable_node(slider.var, WEAPON_COMP_CLASS_PATH))
        _connect(as_weapon, _pin(push, "self"))
        _connect(out(value, slider.var), _pin(push, slider.var))
        _connect(flow, _pin(push, "execute"))
        flow = then(push)

    binds = keep(ed.add_get_member_variable_node(SV.Binds, SETTINGS_CLASS_PATH))
    _connect(settings_out, _pin(binds, "self"))
    binds_out = out(binds, SV.Binds)
    for i, (var, _default) in enumerate(BIND_VARS):
        item = keep(_node(ed, FN_ARR_GET))
        _connect(binds_out, _loose_pin(item, "TargetArray"))
        _set(item, "Index", i)
        put = keep(ed.add_set_member_variable_node(var, WEAPON_COMP_CLASS_PATH))
        _connect(as_weapon, _pin(put, "self"))
        _connect(_loose_pin(item, "Item", is_input=False), _pin(put, var))
        _connect(flow, _pin(put, "execute"))
        flow = then(put)

    ed.add_comment_to_nodes(
        "The player's settings, pushed onto BP_WeaponComponent every frame. "
        "The component never loads them, never casts back here, and keeps the "
        "CDO defaults build_weapons_and_combat.py gave it as a standalone "
        "fallback -- so a pawn with no HUD in front of it still plays with the "
        "documented keys. Guarded on IsValid(Settings) because the alternative "
        "is an Accessed None per frame forever if BeginPlay's load ever failed.",
        made)
    return (flow, out(cast, "CastFailed"), else_(have))


def _author_settings_page(ed, in_exec):
    """Fill WBP_MainMenu's settings page: the caret, the value column, the hint.

    Rows (labels set in the designer, wbp_screens.py): SLIDERS (mouse, then
    scope), DIFFICULTY, BIND_VARS in order, BACK. Left/Right adjust a slider
    or cycle the difficulty, Enter arms a capture on any bind, and every
    change is written to disk on the spot (settings_input.py).

    The bind rows' values are ONE write inside a ForEachLoop over Binds, row
    FIRST_BIND_ROW + index, not one write per bind.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    settings = keep(ed.add_get_member_variable_node(MV.Settings))
    settings_out = out(settings, MV.Settings)
    rows = part(ed, WBP_MAIN_MENU, SETTINGS_ROWS_BOX)

    row = keep(ed.add_get_member_variable_node(MV.MenuRow))
    # The box's rows, then BACK, a row of its own over them: its caret is
    # lit while MenuRow is its number, the last.
    marked = mark_rows(ed, rows, BACK_ROW, out(row, MV.MenuRow), [in_exec])
    on_back = keep(_node(ed, FN_GE_II))
    _connect(out(keep(ed.add_get_member_variable_node(MV.MenuRow)), MV.MenuRow),
             _pin(on_back, "A"))
    _set(on_back, "B", BACK_ROW)
    lit = keep(_node(ed, FN_SELECT_FF))
    _set(lit, "A", 1.0)
    _set(lit, "B", 0.0)
    _connect(out(on_back), _loose_pin(lit, "bPickA"))
    fade = keep(_node(ed, FN_SET_OPACITY))
    _connect(member(ed, part(ed, WBP_MAIN_MENU, SETTINGS_BACK), WBP_MENU_ROW, ROW_CARET),
             _pin(fade, "self"))
    _connect(out(lit), _pin(fade, "InOpacity"))
    _connect(marked, _pin(fade, "execute"))
    flow = (then(fade),)

    # --- the slider rows: the value each is set to --------------------------
    for i, slider in enumerate(SLIDERS):
        value = keep(ed.add_get_member_variable_node(slider.var, SETTINGS_CLASS_PATH))
        _connect(settings_out, _pin(value, "self"))
        value_str = keep(_node(ed, FN_FLOAT_TO_STR))
        _connect(out(value, slider.var), _loose_pin(value_str, "InDouble"))
        flow = row_value(ed, rows, i, out(value_str), flow)

    # --- the difficulty: the name it is set to ------------------------------
    flow = row_value(ed, rows, DIFFICULTY_ROW, author_difficulty_name(ed, settings_out, made), flow)

    # --- the binds, one loop ------------------------------------------------
    binds = keep(ed.add_get_member_variable_node(SV.Binds, SETTINGS_CLASS_PATH))
    _connect(settings_out, _pin(binds, "self"))
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(loop)
    _connect(out(binds, SV.Binds), _loose_pin(loop, "Array"))
    for e in flow:
        _connect(e, _loose_pin(loop, "Exec"))
    index = _loose_pin(loop, "ArrayIndex", is_input=False)
    at_row = keep(_node(ed, FN_ADD_II))
    _connect(index, _pin(at_row, "A"))
    _set(at_row, "B", FIRST_BIND_ROW)
    # Key_GetDisplayName is the only readable spelling of an FKey in 5.8 --
    # Key_GetName does not exist -- and it hands back Text, which SetText takes.
    shown = keep(_node(ed, FN_KEY_DISPLAY))
    _connect(_loose_pin(loop, "ArrayElement", is_input=False), _loose_pin(shown, "Key"))
    row_value(ed, rows, out(at_row),
              ("text", out(shown)),
              [_loose_pin(loop, "LoopBody", is_input=False)])

    # The hint says something different while a capture is armed, or the
    # screen looks frozen: two lines in the designer, one shown.
    arming = keep(ed.add_get_member_variable_node(MV.Capturing))
    hinting = keep(ed.add_branch_node())
    _connect(out(arming, MV.Capturing), _pin(hinting, "Condition"))
    _connect(_loose_pin(loop, "Completed", is_input=False), _pin(hinting, "execute"))
    idle = part(ed, WBP_MAIN_MENU, HINT_IDLE)
    armed = part(ed, WBP_MAIN_MENU, HINT_CAPTURE)
    on_tail = set_shown(ed, idle, False, [set_shown(ed, armed, True, [then(hinting)])])
    off_tail = set_shown(ed, armed, False, [set_shown(ed, idle, True, [else_(hinting)])])

    _author_capture(ed, settings_out, (on_tail, off_tail), made)

    ed.add_comment_to_nodes(
        f"The settings page. {SETTINGS_ROWS} rows: {len(SLIDERS)} sliders, the "
        f"difficulty, the {len(BIND_VARS)} binds, and BACK (drawn over them). Everything it changes is written "
        f"to slot {SETTINGS_SLOT!r} the moment it changes, which is what makes "
        f"it survive a restart -- see _emit_save.",
        made)
