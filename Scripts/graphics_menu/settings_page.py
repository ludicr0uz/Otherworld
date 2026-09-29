"""The settings page: drawing it, and pushing what it holds onto
BP_WeaponComponent every frame. Its input half is settings_input.py; its
constants are settings_rows.py.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from graphics_menu.canvas import (
    COL_CARET, COL_MAIN_HINT, COL_ROW, COL_TITLE, UI_FONT, _draw_texture)
from graphics_menu.settings_input import _author_capture
from graphics_menu.settings_rows import (
    BACK_LABEL, BACK_ROW, BIND_VARS, FIRST_BIND_ROW, SETTINGS_CLASS_PATH,
    SLIDERS,
    SETTINGS_PANEL, SETTINGS_ROWS, SETTINGS_SLOT, SETTINGS_TITLE,
    SET_CARET_X, SET_HINT_OFF, SET_HINT_SCALE, SET_LABEL_X, SET_ROW0_OFF,
    SET_ROW_SCALE, SET_ROW_STEP, SET_TITLE_OFF, SET_TITLE_SCALE, SET_VALUE_X)

FN_ADD = "/Script/Engine.KismetMathLibrary.Add_DoubleDouble"
FN_ARR_GET = "/Script/Engine.KismetArrayLibrary.Array_Get"
FN_BREAK_V2D = "/Script/Engine.KismetMathLibrary.BreakVector2D"
FN_CONV_INT = "/Script/Engine.KismetMathLibrary.Conv_IntToDouble"
FN_DRAW_TEXT = "/Script/Engine.HUD.DrawText"
FN_FLOAT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_DoubleToString"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_GET_PLAYER_PAWN = "/Script/Engine.GameplayStatics.GetPlayerPawn"
FN_IS_VALID = "/Script/Engine.KismetSystemLibrary.IsValid"
FN_KEY_DISPLAY = "/Script/Engine.KismetInputLibrary.Key_GetDisplayName"
FN_MUL = "/Script/Engine.KismetMathLibrary.Multiply_DoubleDouble"
FN_SUB = "/Script/Engine.KismetMathLibrary.Subtract_DoubleDouble"
FN_TEXT_TO_STR = "/Script/Engine.KismetTextLibrary.Conv_TextToString"
FN_VIEWPORT = "/Script/UMG.WidgetLayoutLibrary.GetViewportSize"
NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"
WEAPON_COMP_CLASS_PATH = "/Game/Weapons/BP_WeaponComponent.BP_WeaponComponent_C"
MACRO_FOR_EACH = ("/Engine/EditorBlueprintResources/StandardMacros"
                  ".StandardMacros:ForEachLoop")


def _author_push_settings(ed, x0, y0, in_execs):
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

    got = keep(_at(ed.add_get_member_variable_node("Settings"), x0, y0 + 240))
    settings_out = _pin(got, "Settings", is_input=False)
    ok = keep(_at(_node(ed, FN_IS_VALID), x0 + 240, y0 + 240))
    _connect(settings_out, _pin(ok, "Object"))
    have = keep(_at(ed.add_branch_node(), x0 + 480, y0))
    _connect(_pin(ok, "ReturnValue", is_input=False), _pin(have, "Condition"))
    for e in in_execs:
        _connect(e, _pin(have, "execute"))

    pawn = keep(_at(_node(ed, FN_GET_PLAYER_PAWN), x0 + 480, y0 + 400))
    _set(pawn, "PlayerIndex", 0)
    comp = keep(_at(_node(ed, FN_GET_COMP), x0 + 720, y0 + 400))
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)
    cast = keep(_at(_palette(ed, NODE_CAST_WEAPON), x0 + 980, y0))
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    _connect(BEL.find_then_pin(have), _pin(cast, "execute"))
    as_weapon = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    flow = BEL.find_then_pin(cast)
    for i, slider in enumerate(SLIDERS):
        value = keep(_at(ed.add_get_member_variable_node(slider.var,
                                                         SETTINGS_CLASS_PATH),
                         x0 + 980 + i * 260, y0 + 400 + i * 140))
        _connect(settings_out, _pin(value, "self"))
        push = keep(_at(ed.add_set_member_variable_node(slider.var,
                                                        WEAPON_COMP_CLASS_PATH),
                        x0 + 1240 + i * 260, y0))
        _connect(as_weapon, _pin(push, "self"))
        _connect(_pin(value, slider.var, is_input=False), _pin(push, slider.var))
        _connect(flow, _pin(push, "execute"))
        flow = BEL.find_then_pin(push)

    binds = keep(_at(ed.add_get_member_variable_node("Binds",
                                                     SETTINGS_CLASS_PATH),
                     x0 + 980, y0 + 540))
    _connect(settings_out, _pin(binds, "self"))
    binds_out = _pin(binds, "Binds", is_input=False)
    for i, (var, _default) in enumerate(BIND_VARS):
        item = keep(_at(_node(ed, FN_ARR_GET), x0 + 1760 + i * 280, y0 + 400))
        _connect(binds_out, _loose_pin(item, "TargetArray"))
        _set(item, "Index", i)
        put = keep(_at(ed.add_set_member_variable_node(
            var, WEAPON_COMP_CLASS_PATH), x0 + 1760 + i * 280, y0))
        _connect(as_weapon, _pin(put, "self"))
        _connect(_loose_pin(item, "Item", is_input=False), _pin(put, var))
        _connect(flow, _pin(put, "execute"))
        flow = BEL.find_then_pin(put)

    ed.add_comment_to_nodes(
        "The player's settings, pushed onto BP_WeaponComponent every frame. "
        "The component never loads them, never casts back here, and keeps the "
        "CDO defaults build_weapons_and_combat.py gave it as a standalone "
        "fallback -- so a pawn with no HUD in front of it still plays with the "
        "documented keys. Guarded on IsValid(Settings) because the alternative "
        "is an Accessed None per frame forever if BeginPlay's load ever failed.",
        made)
    return (flow, _pin(cast, "CastFailed", is_input=False),
            BEL.find_else_pin(have))


def _author_settings_page(ed, x0, y0, in_exec):
    """The sensitivity sliders and the seven binds, on the same panel as the title.

    Rows: SLIDERS (mouse, then scope), BIND_VARS in order, BACK. Left/Right
    adjust a slider, Enter arms a capture on any of the seven binds, and every
    change is written to disk on the spot.

    The seven bind rows are ONE pair of DrawTexts inside a ForEachLoop over
    Binds, not seven pairs with their y positions written out -- which is why
    the HUD carries BindLabels as an array rather than as seven literals.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    settings = keep(_at(ed.add_get_member_variable_node("Settings"),
                        x0, y0 + 240))
    settings_out = _pin(settings, "Settings", is_input=False)

    size = keep(_at(_node(ed, FN_VIEWPORT), x0, y0 + 420))
    wh = keep(_at(_node(ed, FN_BREAK_V2D), x0 + 240, y0 + 420))
    _connect(_pin(size, "ReturnValue", is_input=False), _loose_pin(wh, "InVec"))

    def centred(axis, span, py):
        half = keep(_at(_node(ed, FN_MUL), x0 + 480, py))
        _connect(_loose_pin(wh, axis, is_input=False), _pin(half, "A"))
        _set(half, "B", 0.5)
        off = keep(_at(_node(ed, FN_SUB), x0 + 720, py))
        _connect(_pin(half, "ReturnValue", is_input=False), _pin(off, "A"))
        _set(off, "B", span)
        return _pin(off, "ReturnValue", is_input=False)

    panel_x = centred("X", SETTINGS_PANEL[0] / 2.0, y0 + 420)
    panel_y = centred("Y", SETTINGS_PANEL[1] / 2.0, y0 + 560)

    def offset(base, by, px, py):
        n = keep(_at(_node(ed, FN_ADD), px, py))
        _connect(base, _pin(n, "A"))
        _set(n, "B", by)
        return _pin(n, "ReturnValue", is_input=False)

    label_x = offset(panel_x, SET_LABEL_X, x0 + 960, y0 + 420)
    value_x = offset(panel_x, SET_VALUE_X, x0 + 960, y0 + 540)
    caret_x = offset(panel_x, SET_CARET_X, x0 + 960, y0 + 660)

    def row_y(index, py):
        return offset(panel_y, SET_ROW0_OFF + index * SET_ROW_STEP,
                      x0 + 960, py)

    panel = keep(_draw_texture(ed, x0 + 1240, y0, "T_UI_Panel",
                               w=SETTINGS_PANEL[0], h=SETTINGS_PANEL[1]))
    _connect(panel_x, _pin(panel, "ScreenX"))
    _connect(panel_y, _pin(panel, "ScreenY"))
    _connect(in_exec, _pin(panel, "execute"))
    flow = BEL.find_then_pin(panel)

    def text(px, at_x, at_y, scale, color, literal=None, driven=None):
        """One left-aligned row. Left-aligned and not centred on purpose: ten
        rows of different lengths centred individually read as a ragged block,
        and a value column that moves per row cannot be scanned."""
        nonlocal flow
        n = keep(_at(_node(ed, FN_DRAW_TEXT), px, y0))
        if literal is not None:
            _set(n, "Text", literal)
        else:
            _connect(driven, _pin(n, "Text"))
        _set(n, "TextColor", color)
        _set(n, "Scale", scale)
        _set(n, "bScalePosition", "false")
        _set(n, "Font", UI_FONT)
        _connect(at_x, _pin(n, "ScreenX"))
        _connect(at_y, _pin(n, "ScreenY"))
        _connect(flow, _pin(n, "execute"))
        flow = BEL.find_then_pin(n)
        return n

    text(x0 + 1500, label_x,
         offset(panel_y, SET_TITLE_OFF, x0 + 960, y0 + 780),
         SET_TITLE_SCALE, COL_TITLE, literal=SETTINGS_TITLE)

    # The caret, drawn from MenuRow the way the quality panel's is drawn from
    # Quality -- one number, no per-row bookkeeping.
    row = keep(_at(ed.add_get_member_variable_node("MenuRow"), x0 + 960, y0 + 900))
    row_f = keep(_at(_node(ed, FN_CONV_INT), x0 + 1200, y0 + 900))
    _connect(_pin(row, "MenuRow", is_input=False), _pin(row_f, "InInt"))
    caret_off = keep(_at(_node(ed, FN_MUL), x0 + 1440, y0 + 900))
    _connect(_pin(row_f, "ReturnValue", is_input=False), _pin(caret_off, "A"))
    _set(caret_off, "B", SET_ROW_STEP)
    caret_base = row_y(0, y0 + 1020)
    caret_y = keep(_at(_node(ed, FN_ADD), x0 + 1680, y0 + 900))
    _connect(caret_base, _pin(caret_y, "A"))
    _connect(_pin(caret_off, "ReturnValue", is_input=False), _pin(caret_y, "B"))
    text(x0 + 1760, caret_x, _pin(caret_y, "ReturnValue", is_input=False),
         SET_ROW_SCALE, COL_CARET, literal=">")

    # --- the slider rows: a label and the value it is set to ----------------
    for i, slider in enumerate(SLIDERS):
        py = y0 + 1140 + i * 360
        slider_y = row_y(i, py)
        text(x0 + 2020, label_x, slider_y, SET_ROW_SCALE, COL_ROW,
             literal=slider.label)
        value = keep(_at(ed.add_get_member_variable_node(slider.var,
                                                         SETTINGS_CLASS_PATH),
                         x0 + 2020, py + 120))
        _connect(settings_out, _pin(value, "self"))
        value_str = keep(_at(_node(ed, FN_FLOAT_TO_STR), x0 + 2280, py + 120))
        _connect(_pin(value, slider.var, is_input=False),
                 _loose_pin(value_str, "InDouble"))
        text(x0 + 2280, value_x, slider_y, SET_ROW_SCALE, COL_CARET,
             driven=_pin(value_str, "ReturnValue", is_input=False))

    # --- the binds, one loop ------------------------------------------------
    binds = keep(_at(ed.add_get_member_variable_node("Binds",
                                                     SETTINGS_CLASS_PATH),
                     x0 + 2540, y0 + 1260))
    _connect(settings_out, _pin(binds, "self"))
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(_at(loop, x0 + 2800, y0))
    _connect(_pin(binds, "Binds", is_input=False), _loose_pin(loop, "Array"))
    _connect(flow, _loose_pin(loop, "Exec"))
    element = _loose_pin(loop, "ArrayElement", is_input=False)
    index = _loose_pin(loop, "ArrayIndex", is_input=False)

    index_f = keep(_at(_node(ed, FN_CONV_INT), x0 + 3060, y0 + 400))
    _connect(index, _pin(index_f, "InInt"))
    step = keep(_at(_node(ed, FN_MUL), x0 + 3300, y0 + 400))
    _connect(_pin(index_f, "ReturnValue", is_input=False), _pin(step, "A"))
    _set(step, "B", SET_ROW_STEP)
    # Binds[0] is row FIRST_BIND_ROW, directly under the last slider.
    from_panel = keep(_at(_node(ed, FN_ADD), x0 + 3540, y0 + 400))
    _connect(_pin(step, "ReturnValue", is_input=False), _pin(from_panel, "A"))
    _set(from_panel, "B", SET_ROW0_OFF + FIRST_BIND_ROW * SET_ROW_STEP)
    bind_y = keep(_at(_node(ed, FN_ADD), x0 + 3780, y0 + 400))
    _connect(panel_y, _pin(bind_y, "A"))
    _connect(_pin(from_panel, "ReturnValue", is_input=False), _pin(bind_y, "B"))
    bind_y_out = _pin(bind_y, "ReturnValue", is_input=False)

    labels = keep(_at(ed.add_get_member_variable_node("BindLabels"),
                      x0 + 3060, y0 + 560))
    label = keep(_at(_node(ed, FN_ARR_GET), x0 + 3300, y0 + 560))
    _connect(_pin(labels, "BindLabels", is_input=False),
             _loose_pin(label, "TargetArray"))
    _connect(index, _pin(label, "Index"))

    # Key_GetDisplayName is the only readable spelling of an FKey in 5.8 --
    # Key_GetName does not exist -- and it hands back Text, not a String.
    shown = keep(_at(_node(ed, FN_KEY_DISPLAY), x0 + 3300, y0 + 700))
    _connect(element, _loose_pin(shown, "Key"))
    shown_str = keep(_at(_node(ed, FN_TEXT_TO_STR), x0 + 3540, y0 + 700))
    _connect(_pin(shown, "ReturnValue", is_input=False),
             _loose_pin(shown_str, "InText"))

    flow = _loose_pin(loop, "LoopBody", is_input=False)
    text(x0 + 4040, label_x, bind_y_out, SET_ROW_SCALE, COL_ROW,
         driven=_loose_pin(label, "Item", is_input=False))
    text(x0 + 4300, value_x, bind_y_out, SET_ROW_SCALE, COL_CARET,
         driven=_pin(shown_str, "ReturnValue", is_input=False))

    flow = _loose_pin(loop, "Completed", is_input=False)
    text(x0 + 4560, label_x, row_y(BACK_ROW, y0 + 1380), SET_ROW_SCALE,
         COL_ROW, literal=BACK_LABEL)

    # Two draws behind one branch, the same shape the debug row uses: there is
    # no SelectString, and the hint has to say something different while a
    # capture is armed or the screen looks frozen.
    hint_y = offset(panel_y, SET_HINT_OFF, x0 + 960, y0 + 1500)
    arming = keep(_at(ed.add_get_member_variable_node("Capturing"),
                      x0 + 4820, y0 + 400))
    hinting = keep(_at(ed.add_branch_node(), x0 + 4820, y0))
    _connect(_pin(arming, "Capturing", is_input=False), _pin(hinting, "Condition"))
    _connect(flow, _pin(hinting, "execute"))

    flow = BEL.find_then_pin(hinting)
    on_tail = BEL.find_then_pin(
        text(x0 + 5080, label_x, hint_y, SET_HINT_SCALE, COL_CARET,
             literal="press any key to bind it"))
    flow = BEL.find_else_pin(hinting)
    off_tail = BEL.find_then_pin(
        text(x0 + 5340, label_x, hint_y, SET_HINT_SCALE, COL_MAIN_HINT,
             literal="arrows adjust  ·  ENTER rebinds"))

    _author_capture(ed, x0, y0 + 3000, settings_out, (on_tail, off_tail), made)

    ed.add_comment_to_nodes(
        f"The settings page. {SETTINGS_ROWS} rows: {len(SLIDERS)} sliders, the "
        f"{len(BIND_VARS)} binds, and BACK. Everything it changes is written "
        f"to slot {SETTINGS_SLOT!r} the moment it changes, which is what makes "
        f"it survive a restart -- see _emit_save.",
        made)
