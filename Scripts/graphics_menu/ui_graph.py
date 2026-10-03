"""BP_GraphicsMenuHUD's side of the UMG screens: creating them at BeginPlay,
and the node patterns every DrawHUD fragment writes to them with.

The HUD stays the one place that reads the game and polls the keys; the
widgets only show what it hands them. So a fragment is still "read the value,
then write it", with the write a SetText / SetPercent / SetVisibility on a
named widget instead of a DrawText at a computed position.

Every write is guarded the way the canvas draws were: each fragment runs only
on a path where the widget exists, and a cast that fails still carries on to
the rest of the frame.
"""

from combat.graph import (
    BEL, _connect, _declare, _loose_pin, _must_load, _node, _palette, _pin, _set)
from graphics_menu.umg_consts import (
    HIDDEN, ROW_CARET, ROW_VALUE, SCREENS, SHOWN, UI_VAR, WBP_HUD, WBP_MENU_ROW,
    class_path,
)

NODE_CREATE_WIDGET = "UserInterface|CreateWidget"
NODE_CAST_ROW = "Utilities|Casting|CastToWBP_MenuRow"
FN_GET_OWNING_PC = "/Script/Engine.HUD.GetOwningPlayerController"
FN_ADD_TO_VIEWPORT = "/Script/UMG.UserWidget.AddToViewport"
FN_SET_VISIBILITY = "/Script/UMG.Widget.SetVisibility"
FN_SET_OPACITY = "/Script/UMG.Widget.SetRenderOpacity"
FN_SET_TEXT = "/Script/UMG.TextBlock.SetText"
FN_SET_PERCENT = "/Script/UMG.ProgressBar.SetPercent"
FN_CHILD_AT = "/Script/UMG.PanelWidget.GetChildAt"
FN_STR_TO_TEXT = "/Script/Engine.KismetTextLibrary.Conv_StringToText"
FN_SELECT_FLOAT = "/Script/Engine.KismetMathLibrary.SelectFloat"
FN_EQ_II = "/Script/Engine.KismetMathLibrary.EqualEqual_IntInt"
FN_OR = "/Script/Engine.KismetMathLibrary.BooleanOR"
MACRO_FOR_LOOP = ("/Engine/EditorBlueprintResources/StandardMacros"
                  ".StandardMacros:ForLoop")


def _wire(execs, node):
    pin = _pin(node, "execute")
    for e in execs:
        _connect(e, pin)
    return BEL.find_then_pin(node)


# ─── The screens themselves ──────────────────────────────────────────────────

def declare_ui_vars(ed):
    """One reference per screen, typed to its own class so its widgets can be
    read off it without a cast."""
    for var, asset, _z in SCREENS:
        _declare(ed, var, BEL.get_object_reference_type(
            BEL.generated_class(_must_load(asset))))


def author_create_screens(ed, exec_in):
    """BeginPlay: create each screen for the owning player, keep it, add it to
    the viewport -- collapsed, all but WBP_HUD. DrawHUD decides what shows.
    Returns the exec pin that follows."""
    pc = _pin(_node(ed, FN_GET_OWNING_PC), "ReturnValue", is_input=False)
    flow, made = exec_in, []
    for var, asset, z in SCREENS:
        make = _palette(ed, NODE_CREATE_WIDGET)
        _pin(make, "Class").set_pin_value(class_path(asset))
        _connect(pc, _pin(make, "OwningPlayer"))
        _connect(flow, _pin(make, "execute"))
        keep = ed.add_set_member_variable_node(var)
        _connect(_pin(make, "ReturnValue", is_input=False), _pin(keep, var))
        _connect(BEL.find_then_pin(make), _pin(keep, "execute"))
        got = _pin(ed.add_get_member_variable_node(var), var, is_input=False)
        add = _node(ed, FN_ADD_TO_VIEWPORT)
        _connect(got, _pin(add, "self"))
        _set(add, "ZOrder", z)
        _connect(BEL.find_then_pin(keep), _pin(add, "execute"))
        # The HUD screen itself stays up: its Body is what DrawHUD toggles,
        # and its FPS readout shows over every other screen.
        flow = set_shown(ed, got, asset == WBP_HUD, [BEL.find_then_pin(add)])
        made += [make, keep, add]
    ed.add_comment_to_nodes(
        "The UMG screens, created once and kept: the HUD, the M panel, the "
        "title and settings pages, and the death menu. The menus start "
        "collapsed until DrawHUD shows the one the frame is on.", made)
    return flow


def screen(ed, asset):
    """The HUD's reference to the screen built from ``asset``."""
    var = UI_VAR[asset]
    return _pin(ed.add_get_member_variable_node(var), var, is_input=False)


def member(ed, owner, owner_asset, name):
    """Widget ``name`` of ``owner``, an instance of ``owner_asset``'s class."""
    n = ed.add_get_member_variable_node(name, class_path(owner_asset))
    _connect(owner, _pin(n, "self"))
    return _pin(n, name, is_input=False)


def part(ed, asset, name):
    """Widget ``name`` of the HUD's own instance of ``asset``."""
    return member(ed, screen(ed, asset), asset, name)


# ─── Writes ──────────────────────────────────────────────────────────────────

def set_shown(ed, target, shown, execs):
    n = _node(ed, FN_SET_VISIBILITY)
    _connect(target, _pin(n, "self"))
    _set(n, "InVisibility", SHOWN if shown else HIDDEN)
    return _wire(execs, n)


def show_if(ed, target, condition, execs):
    """Shown while ``condition``, collapsed otherwise. Returns both tails."""
    br = ed.add_branch_node()
    _connect(condition, _pin(br, "Condition"))
    _wire(execs, br)
    return (set_shown(ed, target, True, [BEL.find_then_pin(br)]),
            set_shown(ed, target, False, [BEL.find_else_pin(br)]))


def set_text(ed, target, value, execs):
    """TextBlock.SetText. ``value``: a literal, a String pin, or (``.text``) a
    Text pin passed as ``("text", pin)``."""
    n = _node(ed, FN_SET_TEXT)
    _connect(target, _pin(n, "self"))
    if isinstance(value, str):
        _set(n, "InText", value)
    elif isinstance(value, tuple):
        _connect(value[1], _pin(n, "InText"))
    else:
        conv = _node(ed, FN_STR_TO_TEXT)
        _connect(value, _pin(conv, "InString"))
        _connect(_pin(conv, "ReturnValue", is_input=False), _pin(n, "InText"))
    return _wire(execs, n)


def set_percent(ed, bar, fraction, execs):
    n = _node(ed, FN_SET_PERCENT)
    _connect(bar, _pin(n, "self"))
    _connect(fraction, _pin(n, "InPercent"))
    return _wire(execs, n)


# ─── Menu rows ───────────────────────────────────────────────────────────────

def row_at(ed, box, index, execs):
    """Row ``index`` of a stack of WBP_MenuRows: (row pin, then, cast-failed).

    GetChildAt hands back a plain Widget; the cast is what makes its Caret
    and Value readable. ``index`` is an int literal or an int pin.
    """
    child = _node(ed, FN_CHILD_AT)
    _connect(box, _pin(child, "self"))
    if isinstance(index, int):
        _set(child, "Index", index)
    else:
        _connect(index, _pin(child, "Index"))
    cast = _palette(ed, NODE_CAST_ROW)
    _connect(_pin(child, "ReturnValue", is_input=False), _pin(cast, "Object"))
    then = _wire(execs, cast)
    return (_loose_pin(cast, "AsWBPMenuRow", is_input=False), then,
            _pin(cast, "CastFailed", is_input=False))


def row_value(ed, box, index, value, execs):
    """Row ``index``'s value column := ``value`` (see set_text). Returns the
    exec pins that carry on, the cast-failed one included."""
    row, then, failed = row_at(ed, box, index, execs)
    target = member(ed, row, WBP_MENU_ROW, ROW_VALUE)
    return (set_text(ed, target, value, [then]), failed)


def mark_rows(ed, box, count, selected, execs, also=None):
    """Light the caret of row ``selected`` (an int pin) and dim the rest.
    ``also``: a second int pin whose row is lit too (the M panel's row under
    the cursor, beside the one its preset is on).

    One loop over the rows rather than one caret moved by arithmetic: the
    selection is a property of the row, which is what lets the rows be laid
    out by the designer. Opacity rather than visibility, so an unselected row
    keeps the caret's width and the labels stay in one column.
    Returns the loop's Completed pin.
    """
    loop = ed.add_macro_node(MACRO_FOR_LOOP)
    if not loop:
        raise RuntimeError("could not create the ForLoop macro node")
    loop
    _set(loop, "FirstIndex", 0)
    _set(loop, "LastIndex", count - 1)
    for e in execs:
        _connect(e, _pin(loop, "execute"))
    index = _loose_pin(loop, "Index", is_input=False)
    row, then, _failed = row_at(ed, box, index, [_loose_pin(loop, "LoopBody", is_input=False)])
    hit = _node(ed, FN_EQ_II)
    _connect(index, _pin(hit, "A"))
    _connect(selected, _pin(hit, "B"))
    picked = _pin(hit, "ReturnValue", is_input=False)
    if also is not None:
        hover = _node(ed, FN_EQ_II)
        _connect(index, _pin(hover, "A"))
        _connect(also, _pin(hover, "B"))
        either = _node(ed, FN_OR)
        _connect(picked, _pin(either, "A"))
        _connect(_pin(hover, "ReturnValue", is_input=False), _pin(either, "B"))
        picked = _pin(either, "ReturnValue", is_input=False)
    lit = _node(ed, FN_SELECT_FLOAT)
    _set(lit, "A", 1.0)
    _set(lit, "B", 0.0)
    _connect(picked, _pin(lit, "bPickA"))
    fade = _node(ed, FN_SET_OPACITY)
    _connect(member(ed, row, WBP_MENU_ROW, ROW_CARET), _pin(fade, "self"))
    _connect(_pin(lit, "ReturnValue", is_input=False), _pin(fade, "InOpacity"))
    _wire([then], fade)
    return _loose_pin(loop, "Completed", is_input=False)
