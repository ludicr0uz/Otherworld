"""What save-and-exit puts on screen: its row in the M panel, and the banner.

The banner is top centre while the countdown runs ("SAVING AND EXITING IN  12",
whole seconds rounded up so it never reads 0 while waiting), and for
EXIT_CALLED_OFF_SHOWN_S after a hit called it off. The logic is save_exit.py's
on Tick; this only reads its variables.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _pin, _set
from graphics_menu.canvas import COL_ROW, UI_FONT
from graphics_menu.profile_consts import (
    COL_EXIT_BANNER, COL_EXIT_CALLED_OFF, EXIT_AT_VAR, EXIT_BANNER_HALF_W,
    EXIT_BANNER_PREFIX, EXIT_BANNER_SCALE, EXIT_BANNER_Y, EXIT_CALLED_OFF_SHOWN_S,
    EXIT_CALLED_OFF_TEXT, EXIT_CALLED_OFF_VAR, EXIT_PENDING_VAR, EXIT_ROW_LABEL,
)

FN_DRAW_TEXT = "/Script/Engine.HUD.DrawText"
FN_TIME_SECONDS = "/Script/Engine.GameplayStatics.GetTimeSeconds"
FN_SUB = "/Script/Engine.KismetMathLibrary.Subtract_DoubleDouble"
FN_MUL = "/Script/Engine.KismetMathLibrary.Multiply_DoubleDouble"
FN_LESS = "/Script/Engine.KismetMathLibrary.Less_DoubleDouble"
FN_CEIL = "/Script/Engine.KismetMathLibrary.FCeil"
FN_INT_TO_STR = "/Script/Engine.KismetStringLibrary.Conv_IntToString"
FN_CONCAT = "/Script/Engine.KismetStringLibrary.Concat_StrStr"
FN_VIEWPORT = "/Script/UMG.WidgetLayoutLibrary.GetViewportSize"
FN_BREAK_V2D = "/Script/Engine.KismetMathLibrary.BreakVector2D"


def _text(ed, text, color, x, y, scale, in_execs, at_x, at_y, made):
    """A DrawText; ``text`` and ``x`` are literals or pins."""
    n = _at(_node(ed, FN_DRAW_TEXT), at_x, at_y)
    for name, v in (("Text", text), ("ScreenX", x)):
        if isinstance(v, (str, float)):
            _set(n, name, v)
        else:
            _connect(v, _pin(n, name))
    _set(n, "TextColor", color)
    _set(n, "ScreenY", y)
    _set(n, "Scale", scale)
    _set(n, "bScalePosition", "false")
    _set(n, "Font", UI_FONT)
    for e in in_execs:
        _connect(e, _pin(n, "execute"))
    made.append(n)
    return BEL.find_then_pin(n)


def author_exit_row(ed, x, y, scale, in_execs, at_x, at_y):
    """The panel's "[X]   save and exit" line. Returns the exec that follows."""
    made = []
    return _text(ed, EXIT_ROW_LABEL, COL_ROW, x, y, scale, in_execs, at_x, at_y, made)


def author_exit_banner(ed, x0, y0, in_execs):
    """The countdown, or the called-off notice. Returns the exec tails."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def get(var, px, py):
        return _pin(keep(_at(ed.add_get_member_variable_node(var), px, py)), var,
                    is_input=False)

    br = keep(_at(ed.add_branch_node(), x0, y0))
    _connect(get(EXIT_PENDING_VAR, x0 - 240, y0 + 200), _pin(br, "Condition"))
    for e in in_execs:
        _connect(e, _pin(br, "execute"))
    now = _pin(keep(_at(_node(ed, FN_TIME_SECONDS), x0, y0 + 600)), "ReturnValue",
               is_input=False)

    size = keep(_at(_node(ed, FN_VIEWPORT), x0 + 240, y0 + 800))
    wh = keep(_at(_node(ed, FN_BREAK_V2D), x0 + 480, y0 + 800))
    _connect(_pin(size, "ReturnValue", is_input=False), _loose_pin(wh, "InVec"))
    half = keep(_at(_node(ed, FN_MUL), x0 + 720, y0 + 800))
    _connect(_loose_pin(wh, "X", is_input=False), _pin(half, "A"))
    _set(half, "B", 0.5)
    left = keep(_at(_node(ed, FN_SUB), x0 + 960, y0 + 800))
    _connect(_pin(half, "ReturnValue", is_input=False), _pin(left, "A"))
    _set(left, "B", EXIT_BANNER_HALF_W)
    left_out = _pin(left, "ReturnValue", is_input=False)

    # --- the countdown -----------------------------------------------------
    remaining = keep(_at(_node(ed, FN_SUB), x0 + 240, y0 + 400))
    _connect(get(EXIT_AT_VAR, x0, y0 + 400), _pin(remaining, "A"))
    _connect(now, _pin(remaining, "B"))
    whole = keep(_at(_node(ed, FN_CEIL), x0 + 480, y0 + 400))
    _connect(_pin(remaining, "ReturnValue", is_input=False), _pin(whole, "A"))
    digits = keep(_at(_node(ed, FN_INT_TO_STR), x0 + 720, y0 + 400))
    _connect(_pin(whole, "ReturnValue", is_input=False), _pin(digits, "InInt"))
    line = keep(_at(_node(ed, FN_CONCAT), x0 + 960, y0 + 400))
    _set(line, "A", EXIT_BANNER_PREFIX)
    _connect(_pin(digits, "ReturnValue", is_input=False), _pin(line, "B"))
    counting = _text(ed, _pin(line, "ReturnValue", is_input=False), COL_EXIT_BANNER,
                     left_out, EXIT_BANNER_Y, EXIT_BANNER_SCALE,
                     [BEL.find_then_pin(br)], x0 + 1200, y0, made)

    # --- or, for a moment after a hit, why it stopped -------------------------
    ago = keep(_at(_node(ed, FN_SUB), x0 + 240, y0 + 1000))
    _connect(now, _pin(ago, "A"))
    _connect(get(EXIT_CALLED_OFF_VAR, x0, y0 + 1000), _pin(ago, "B"))
    recent = keep(_at(_node(ed, FN_LESS), x0 + 480, y0 + 1000))
    _connect(_pin(ago, "ReturnValue", is_input=False), _pin(recent, "A"))
    _set(recent, "B", EXIT_CALLED_OFF_SHOWN_S)
    shown = keep(_at(ed.add_branch_node(), x0 + 1200, y0 + 600))
    _connect(_pin(recent, "ReturnValue", is_input=False), _pin(shown, "Condition"))
    _connect(BEL.find_else_pin(br), _pin(shown, "execute"))
    called_off = _text(ed, EXIT_CALLED_OFF_TEXT, COL_EXIT_CALLED_OFF, left_out,
                       EXIT_BANNER_Y, EXIT_BANNER_SCALE, [BEL.find_then_pin(shown)],
                       x0 + 1460, y0 + 600, made)
    ed.add_comment_to_nodes(
        "Save and exit: the countdown while it runs, and for "
        f"{EXIT_CALLED_OFF_SHOWN_S:.0f} s after a hit calls it off, why it stopped.",
        made)
    return [counting, called_off, BEL.find_else_pin(shown)]
