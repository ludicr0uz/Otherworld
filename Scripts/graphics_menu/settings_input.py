"""The settings page's input half: rebinding capture, the arrow-key nudges,
BACK, and the save written after every change.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _pin, _set
from graphics_menu.menu_nav import (
    NAV_LEFT, NAV_RIGHT, _emit_accept, _emit_row_nav)
from graphics_menu.settings_rows import (
    BACK_ROW, FIRST_BIND_ROW, PAGE_TITLE, SETTINGS_CLASS_PATH, SETTINGS_SLOT,
    SETTINGS_USER_INDEX, SLIDERS)

FN_WAS_PRESSED = "/Script/Engine.PlayerController.WasInputKeyJustPressed"
FN_GET_OWNING_PC = "/Script/Engine.HUD.GetOwningPlayerController"
FN_WRITE_SAVE = "/Script/Engine.GameplayStatics.SaveGameToSlot"
FN_ARR_SET = "/Script/Engine.KismetArrayLibrary.Array_Set"
FN_SUB_II = "/Script/Engine.KismetMathLibrary.Subtract_IntInt"
FN_EQ_II = "/Script/Engine.KismetMathLibrary.EqualEqual_IntInt"
FN_GE_II = "/Script/Engine.KismetMathLibrary.GreaterEqual_IntInt"
FN_OR = "/Script/Engine.KismetMathLibrary.BooleanOR"
FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_ADD = "/Script/Engine.KismetMathLibrary.Add_DoubleDouble"
FN_FCLAMP = "/Script/Engine.KismetMathLibrary.FClamp"
FN_SELECT_FLOAT = "/Script/Engine.KismetMathLibrary.SelectFloat"
MACRO_FOR_EACH = ("/Engine/EditorBlueprintResources/StandardMacros"
                  ".StandardMacros:ForEachLoop")


def _emit_save(ed, settings_out, in_exec, x, y):
    """Write BP_Settings back to its slot. Called after every single change.

    On the change and not on leaving the page: a game quit from the settings
    screen still has to remember what was set, and there is no other moment
    this HUD is guaranteed to see.
    """
    n = _at(_node(ed, FN_WRITE_SAVE), x, y)
    _connect(settings_out, _pin(n, "SaveGameObject"))
    _set(n, "SlotName", SETTINGS_SLOT)
    _set(n, "UserIndex", SETTINGS_USER_INDEX)
    _connect(in_exec, _pin(n, "execute"))
    return BEL.find_then_pin(n), n


def _author_capture(ed, x0, y0, settings_out, in_execs, made):
    """The input half of the settings page: capture first, then everything else.

    THE ORDER OF THESE TWO ARMS IS LOAD-BEARING. The capture poll is authored
    and branched on BEFORE the row is activated, because Enter is what arms a
    capture -- and Enter is still "just pressed" for the rest of that frame. A
    capture poll that ran after the activation would see it and instantly bind
    the accept key to whatever row the caret was on, which is a settings screen
    that eats itself the first time it is used. Branching on Capturing puts
    them in different frames as well as in different arms, and both of those
    have to be true.
    """
    def keep(n):
        made.append(n)
        return n

    pc = keep(_at(_node(ed, FN_GET_OWNING_PC), x0, y0 + 240))
    pc_out = _pin(pc, "ReturnValue", is_input=False)

    armed = keep(_at(ed.add_get_member_variable_node("Capturing"), x0, y0 + 400))
    listening = keep(_at(ed.add_branch_node(), x0 + 260, y0))
    _connect(_pin(armed, "Capturing", is_input=False), _pin(listening, "Condition"))
    for e in in_execs:
        _connect(e, _pin(listening, "execute"))

    # --- armed: the next key in KEY_POOL that goes down becomes the bind ------
    pool = keep(_at(ed.add_get_member_variable_node("KeyPool"), x0 + 520, y0 + 400))
    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(_at(loop, x0 + 780, y0))
    _connect(_pin(pool, "KeyPool", is_input=False), _loose_pin(loop, "Array"))
    _connect(BEL.find_then_pin(listening), _loose_pin(loop, "Exec"))
    candidate = _loose_pin(loop, "ArrayElement", is_input=False)

    hit = keep(_at(_node(ed, FN_WAS_PRESSED), x0 + 1040, y0 + 400))
    _connect(pc_out, _pin(hit, "self"))
    _connect(candidate, _pin(hit, "Key"))
    took = keep(_at(ed.add_branch_node(), x0 + 1300, y0))
    _connect(_pin(hit, "ReturnValue", is_input=False), _pin(took, "Condition"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(took, "execute"))

    # Binds[MenuRow - FIRST_BIND_ROW]: the sliders sit above the binds, so the
    # subtraction is the whole of that mapping.
    row = keep(_at(ed.add_get_member_variable_node("MenuRow"), x0 + 1300, y0 + 400))
    slot = keep(_at(_node(ed, FN_SUB_II), x0 + 1560, y0 + 400))
    _connect(_pin(row, "MenuRow", is_input=False), _pin(slot, "A"))
    _set(slot, "B", FIRST_BIND_ROW)
    binds = keep(_at(ed.add_get_member_variable_node("Binds",
                                                     SETTINGS_CLASS_PATH),
                     x0 + 1300, y0 + 540))
    _connect(settings_out, _pin(binds, "self"))
    write = keep(_at(_node(ed, FN_ARR_SET), x0 + 1820, y0))
    _connect(_pin(binds, "Binds", is_input=False), _loose_pin(write, "TargetArray"))
    _connect(_pin(slot, "ReturnValue", is_input=False), _pin(write, "Index"))
    _connect(candidate, _loose_pin(write, "Item"))
    _connect(BEL.find_then_pin(took), _pin(write, "execute"))
    done = keep(_at(ed.add_set_member_variable_node("Capturing"), x0 + 2080, y0))
    _set(done, "Capturing", "false")
    _connect(BEL.find_then_pin(write), _pin(done, "execute"))
    _, writer = _emit_save(ed, settings_out, BEL.find_then_pin(done),
                           x0 + 2340, y0)
    made.append(writer)

    # --- not armed: move the caret, nudge the sensitivity, take the row -------
    moved, nav = _emit_row_nav(ed, pc_out, BACK_ROW,
                               BEL.find_else_pin(listening), x0 + 520, y0 + 1200)
    made += nav

    left = keep(_at(_node(ed, FN_WAS_PRESSED), x0 + 2000, y0 + 1200))
    _connect(pc_out, _pin(left, "self"))
    _set(left, "Key", NAV_LEFT)
    right = keep(_at(_node(ed, FN_WAS_PRESSED), x0 + 2000, y0 + 1340))
    _connect(pc_out, _pin(right, "self"))
    _set(right, "Key", NAV_RIGHT)
    right_out = _pin(right, "ReturnValue", is_input=False)
    either = keep(_at(_node(ed, FN_OR), x0 + 2260, y0 + 1200))
    _connect(_pin(left, "ReturnValue", is_input=False), _pin(either, "A"))
    _connect(right_out, _pin(either, "B"))
    either_out = _pin(either, "ReturnValue", is_input=False)

    # One nudge block per slider, in series: each one's "not me" arm and its
    # saved tail both carry on into the next, and the last pair into accept.
    flow = moved
    for i, slider in enumerate(SLIDERS):
        flow = _emit_nudge(ed, slider, i, settings_out, either_out, right_out,
                           flow, x0 + 2520, y0 + 1600 + i * 700, made)

    go = _emit_accept(ed, pc_out, x0 + 4100, y0 + 1000, flow, made)

    # BACK, or arm a capture. Enter means nothing on a slider row -- the arrows
    # are its control, and arming a capture there would bind a key to a row
    # that has none -- so only rows from FIRST_BIND_ROW down arm one.
    leaving = keep(_at(_node(ed, FN_EQ_II), x0 + 4360, y0 + 1400))
    _connect(_pin(keep(_at(ed.add_get_member_variable_node("MenuRow"),
                           x0 + 4100, y0 + 1400)), "MenuRow", is_input=False),
             _pin(leaving, "A"))
    _set(leaving, "B", BACK_ROW)
    back = keep(_at(ed.add_branch_node(), x0 + 4620, y0 + 1000))
    _connect(_pin(leaving, "ReturnValue", is_input=False), _pin(back, "Condition"))
    _connect(BEL.find_then_pin(go), _pin(back, "execute"))

    to_title = keep(_at(ed.add_set_member_variable_node("MenuPage"),
                        x0 + 4880, y0 + 1000))
    _set(to_title, "MenuPage", PAGE_TITLE)
    _connect(BEL.find_then_pin(back), _pin(to_title, "execute"))
    home = keep(_at(ed.add_set_member_variable_node("MenuRow"),
                    x0 + 5140, y0 + 1000))
    _set(home, "MenuRow", 0)
    _connect(BEL.find_then_pin(to_title), _pin(home, "execute"))

    bindable = keep(_at(_node(ed, FN_GE_II), x0 + 4880, y0 + 1600))
    _connect(_pin(keep(_at(ed.add_get_member_variable_node("MenuRow"),
                           x0 + 4620, y0 + 1600)), "MenuRow", is_input=False),
             _pin(bindable, "A"))
    _set(bindable, "B", FIRST_BIND_ROW)
    arming = keep(_at(ed.add_branch_node(), x0 + 5140, y0 + 1600))
    _connect(_pin(bindable, "ReturnValue", is_input=False), _pin(arming, "Condition"))
    _connect(BEL.find_else_pin(back), _pin(arming, "execute"))
    arm = keep(_at(ed.add_set_member_variable_node("Capturing"),
                   x0 + 5400, y0 + 1600))
    _set(arm, "Capturing", "true")
    _connect(BEL.find_then_pin(arming), _pin(arm, "execute"))


def _emit_nudge(ed, slider, row, settings_out, either_out, right_out, in_execs,
                x0, y0, made):
    """Left/Right on ``row``: step ``slider.var`` on BP_Settings and save it.

    One write with a signed step rather than two arms with the same two writes
    in them: the pair would drift, and the clamp would end up on only one of
    them. Returns the exec pins to carry on from -- the saved tail and the
    "not this row" arm.
    """
    def keep(n):
        made.append(n)
        return n

    here = keep(_at(_node(ed, FN_EQ_II), x0 + 260, y0 + 480))
    _connect(_pin(keep(_at(ed.add_get_member_variable_node("MenuRow"),
                           x0, y0 + 480)), "MenuRow", is_input=False),
             _pin(here, "A"))
    _set(here, "B", row)
    adjusting = keep(_at(_node(ed, FN_AND), x0 + 520, y0 + 200))
    _connect(either_out, _pin(adjusting, "A"))
    _connect(_pin(here, "ReturnValue", is_input=False), _pin(adjusting, "B"))
    nudging = keep(_at(ed.add_branch_node(), x0 + 780, y0))
    _connect(_pin(adjusting, "ReturnValue", is_input=False), _pin(nudging, "Condition"))
    for e in in_execs:
        _connect(e, _pin(nudging, "execute"))

    delta = keep(_at(_node(ed, FN_SELECT_FLOAT), x0 + 780, y0 + 340))
    _set(delta, "A", slider.step)
    _set(delta, "B", -slider.step)
    _connect(right_out, _loose_pin(delta, "bPickA"))
    now = keep(_at(ed.add_get_member_variable_node(slider.var,
                                                   SETTINGS_CLASS_PATH),
                   x0 + 780, y0 + 480))
    _connect(settings_out, _pin(now, "self"))
    total = keep(_at(_node(ed, FN_ADD), x0 + 1040, y0 + 400))
    _connect(_pin(now, slider.var, is_input=False), _pin(total, "A"))
    _connect(_pin(delta, "ReturnValue", is_input=False), _pin(total, "B"))
    held = keep(_at(_node(ed, FN_FCLAMP), x0 + 1300, y0 + 400))
    _connect(_pin(total, "ReturnValue", is_input=False), _loose_pin(held, "Value"))
    _set(held, "Min", slider.lo)
    _set(held, "Max", slider.hi)
    store = keep(_at(ed.add_set_member_variable_node(slider.var,
                                                     SETTINGS_CLASS_PATH),
                     x0 + 1560, y0))
    _connect(settings_out, _pin(store, "self"))
    _connect(_pin(held, "ReturnValue", is_input=False), _pin(store, slider.var))
    _connect(BEL.find_then_pin(nudging), _pin(store, "execute"))
    saved, writer = _emit_save(ed, settings_out, BEL.find_then_pin(store),
                               x0 + 1820, y0)
    made.append(writer)
    return (saved, BEL.find_else_pin(nudging))
